import asyncio
import uuid
import sys
import os
from typing import Optional

# Allow shared imports from parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from shared.excel_reader import get_all_person_ids, get_events_for_patient
from shared.gemini_embedder import embed_text
from shared.qdrant_store import (
    get_client,
    ensure_collection,
    upsert_vectors,
    delete_patient_vectors,
    patient_has_vectors,
)

from app.config import settings
from app.core.logging import logger
from app.services.chunker_service import chunk_text
from app.utils.job_tracker import (
    create_job,
    update_job,
    increment_processed,
    increment_failed,
)
from app.models.schemas import PatientEmbedResponse


async def _embed_single_patient(
    person_id: str,
    input_file: str,
    is_reembed: bool = False,
) -> PatientEmbedResponse:
    """
    Core logic — embed all events for one patient into Qdrant.

    Steps:
    1. Fetch all event rows for this patient from input Excel
    2. For each event → chunk plain_scrubbed_text
    3. Embed each chunk via gemini-embedding-001
    4. Upsert into Qdrant with full payload
    """
    qdrant = get_client(settings.qdrant_host, settings.qdrant_port)
    ensure_collection(qdrant, settings.qdrant_collection)

    # Delete existing vectors if re-embedding
    if is_reembed:
        delete_patient_vectors(qdrant, settings.qdrant_collection, person_id)
        logger.info(f"Deleted existing vectors | person_id={person_id}")

    events = get_events_for_patient(person_id, input_file)

    if not events:
        return PatientEmbedResponse(
            person_id        = person_id,
            status           = "failed",
            chunks_stored    = 0,
            events_processed = 0,
            message          = f"No events found for person_id '{person_id}' in input Excel.",
        )

    total_chunks    = 0
    events_done     = 0
    semaphore       = asyncio.Semaphore(3)  # max 3 concurrent embed calls per patient

    async def embed_chunk(event_id, doc_type, chunk_idx, chunk):
        async with semaphore:
            vector = await embed_text(chunk, settings.gemini_embedding_model)
            upsert_vectors(
                client      = qdrant,
                collection  = settings.qdrant_collection,
                person_id   = person_id,
                event_id    = event_id,
                chunk_index = chunk_idx,
                doc_type    = doc_type,
                text        = chunk,
                vector      = vector,
            )

    for event in events:
        event_id  = event["event_id"]
        doc_type  = event["doc_type"]
        raw_text  = event["plain_scrubbed_text"]

        if not raw_text.strip():
            logger.warning(f"Empty plain_scrubbed_text | person_id={person_id} | event_id={event_id}")
            continue

        chunks = chunk_text(raw_text, settings.chunk_size, settings.chunk_overlap)
        logger.info(f"Chunked | person_id={person_id} | event_id={event_id} | chunks={len(chunks)}")

        tasks = [
            embed_chunk(event_id, doc_type, idx, chunk)
            for idx, chunk in enumerate(chunks)
        ]
        await asyncio.gather(*tasks)

        total_chunks += len(chunks)
        events_done  += 1

    status = "re_embedded" if is_reembed else "embedded"
    logger.info(
        f"Patient embedded | person_id={person_id} | "
        f"events={events_done} | chunks={total_chunks}"
    )

    return PatientEmbedResponse(
        person_id        = person_id,
        status           = status,
        chunks_stored    = total_chunks,
        events_processed = events_done,
        message          = f"Successfully embedded {events_done} events, {total_chunks} chunks.",
    )


async def run_bulk_embed(job_id: str, file_path: Optional[str] = None) -> None:
    """
    Background task — embed ALL patients from input Excel.
    Updates job tracker throughout.
    """
    input_file = file_path or settings.input_file
    update_job(job_id, status="processing")

    try:
        person_ids = get_all_person_ids(input_file)
        total      = len(person_ids)
        update_job(job_id, total=total)

        if total == 0:
            update_job(job_id, status="completed", message="No patients found.")
            return

        # Process patients concurrently (max 5 at a time)
        semaphore = asyncio.Semaphore(settings.max_concurrent_embed if hasattr(settings, "max_concurrent_embed") else 5)

        async def process_one(person_id: str):
            async with semaphore:
                try:
                    await _embed_single_patient(person_id, input_file, is_reembed=False)
                    increment_processed(job_id)
                    logger.info(f"Bulk embed progress | {job_id} | {person_id} done")
                except Exception as e:
                    increment_failed(job_id, person_id, str(e))
                    logger.error(f"Bulk embed failed | person_id={person_id} | {e}")

        tasks = [process_one(pid) for pid in person_ids]
        await asyncio.gather(*tasks)

        from app.utils.job_tracker import get_job
        job     = get_job(job_id)
        failed  = job.get("failed", 0)
        done    = job.get("processed", 0)

        update_job(
            job_id,
            status  = "completed",
            message = f"Completed. {done} embedded, {failed} failed.",
        )
        logger.info(f"Bulk embed job completed | job_id={job_id}")

    except Exception as e:
        update_job(job_id, status="failed", message=str(e))
        logger.error(f"Bulk embed job failed | job_id={job_id} | {e}")


async def embed_single_patient(
    person_id: str,
    file_path: Optional[str] = None,
) -> PatientEmbedResponse:
    """
    Public function — embed or re-embed one patient.
    Called by the API endpoint and also by the summary service on update.
    """
    input_file = file_path or settings.input_file

    qdrant     = get_client(settings.qdrant_host, settings.qdrant_port)
    is_reembed = patient_has_vectors(qdrant, settings.qdrant_collection, person_id)

    return await _embed_single_patient(person_id, input_file, is_reembed=is_reembed)


def start_bulk_embed_job(file_path: Optional[str] = None) -> str:
    """
    Create job entry and schedule bulk embed as background task.
    Returns job_id immediately.
    """
    job_id = str(uuid.uuid4())
    create_job(job_id)
    asyncio.create_task(run_bulk_embed(job_id, file_path))
    logger.info(f"Bulk embed job queued | job_id={job_id}")
    return job_id
