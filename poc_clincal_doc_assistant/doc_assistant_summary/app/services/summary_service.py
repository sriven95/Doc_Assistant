import asyncio
import uuid
from typing import Dict, Optional
from datetime import datetime

from app.config import settings
from app.core.logging import logger
from app.models.schemas import SummaryResponse, JobStatusResponse
from app.services.excel_service import (
    get_all_patients,
    get_events_for_patient,
    get_single_event,
    get_existing_summary,
    write_summary,
)
from app.services.gemini_service import (
    generate_summary,
    generate_summaries_batch,
)
from app.utils.prompt_builder import format_summary_chain


# ── In-memory job tracker ──────────────────────────────────────────────────────
# For POC this is fine.
# For production: replace with Redis or a jobs table in PostgreSQL.
_jobs: Dict[str, Dict] = {}


def get_job_status(job_id: str) -> Optional[Dict]:
    """Return job tracking dict for a given job_id, or None."""
    return _jobs.get(job_id)


# ── FLOW A — Bulk one-time generation ─────────────────────────────────────────

async def _run_bulk_generation(
    job_id: str,
    file_path: Optional[str] = None,
) -> None:
    """
    Background coroutine — processes all patients in the input Excel.

    Steps:
    1. Read and group input Excel by person_id
    2. Keep events in natural Excel row order (newest → oldest)
    3. Send all patients to Gemini concurrently (bounded semaphore)
    4. Write each generated summary to output Excel
    5. Update job tracker throughout
    """
    _jobs[job_id]["status"]     = "processing"
    _jobs[job_id]["started_at"] = datetime.utcnow().isoformat()
    logger.info(f"Bulk job started | job_id={job_id}")

    try:
        # Step 1 — Read and group
        patients = get_all_patients(file_path)
        total    = len(patients)
        _jobs[job_id]["total"] = total

        if total == 0:
            _jobs[job_id]["status"]  = "completed"
            _jobs[job_id]["message"] = "No patients found in input file."
            logger.warning(f"Bulk job — no patients found | job_id={job_id}")
            return

        # Step 2 + 3 — Generate all summaries concurrently
        results, errors = await generate_summaries_batch(patients)

        # Step 4 — Write each result to output Excel
        processed_count = 0
        for person_id, gemini_output in results.items():
            events    = patients[person_id]
            event_ids = [e["event_id"] for e in events]
            now       = datetime.utcnow().isoformat()

            summary_chain = format_summary_chain(
                gemini_output.event_summaries, event_ids
            )

            write_summary(
                person_id           = person_id,
                main_subject        = gemini_output.main_subject,
                summary_chain       = summary_chain,
                processed_event_ids = event_ids,
                generated_at        = now,
            )
            processed_count                += 1
            _jobs[job_id]["processed"]      = processed_count

        # Step 5 — Mark complete
        _jobs[job_id]["status"]  = "completed"
        _jobs[job_id]["failed"]  = len(errors)
        _jobs[job_id]["errors"]  = errors
        _jobs[job_id]["message"] = (
            f"Completed. {processed_count} summaries generated, "
            f"{len(errors)} failed."
        )
        logger.info(
            f"Bulk job completed | job_id={job_id} | "
            f"processed={processed_count} | failed={len(errors)}"
        )

    except Exception as e:
        _jobs[job_id]["status"]  = "failed"
        _jobs[job_id]["message"] = str(e)
        logger.error(f"Bulk job failed | job_id={job_id} | error={e}")


def start_bulk_job(file_path: Optional[str] = None) -> JobStatusResponse:
    """
    Kick off bulk generation as a background task.
    Returns immediately with a job_id — caller polls /status/{job_id}.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id"    : job_id,
        "status"    : "queued",
        "total"     : 0,
        "processed" : 0,
        "failed"    : 0,
        "errors"    : {},
        "message"   : "Job queued and will start shortly.",
    }

    asyncio.create_task(_run_bulk_generation(job_id, file_path))
    logger.info(f"Bulk job queued | job_id={job_id}")

    return JobStatusResponse(
        job_id         = job_id,
        status         = "queued",
        total_patients = 0,
        processed      = 0,
        failed         = 0,
        message        = "Bulk generation started. Poll /api/v1/status/{job_id} for progress.",
    )


# ── FLOW B — Update (patient returns with new event) ──────────────────────────

async def update_patient_summary(
    person_id: str,
    event_id: str,
) -> SummaryResponse:
    """
    Update flow triggered when a patient returns with a new event_id.

    Decision tree:
    1. Does a summary exist for person_id?
       NO  → Generate fresh summary (Flow A for one patient)
    2. Is event_id already in processed_event_ids?
       YES → Return existing summary, status = already_processed
    3. New event_id →
       - Fetch all existing events from input Excel
       - Place new event at TOP (it is the newest)
       - Full regeneration via Gemini
       - Overwrite output Excel row
    """
    logger.info(f"Update requested | person_id={person_id} | event_id={event_id}")
    existing = get_existing_summary(person_id)

    # ── Case 1: No existing summary → create fresh ──────────────────────────
    if existing is None:
        logger.info(f"No existing summary found — creating | person_id={person_id}")
        events = get_events_for_patient(person_id)

        if not events:
            return SummaryResponse(
                person_id = person_id,
                status    = "failed",
                message   = (
                    f"No events found for person_id '{person_id}' in input Excel."
                ),
            )

        gemini_output = await generate_summary(events)
        event_ids     = [e["event_id"] for e in events]
        now           = datetime.utcnow().isoformat()
        summary_chain = format_summary_chain(
            gemini_output.event_summaries, event_ids
        )

        write_summary(
            person_id           = person_id,
            main_subject        = gemini_output.main_subject,
            summary_chain       = summary_chain,
            processed_event_ids = event_ids,
            generated_at        = now,
        )

        return SummaryResponse(
            person_id           = person_id,
            status              = "created",
            main_subject        = gemini_output.main_subject,
            summary_chain       = summary_chain,
            processed_event_ids = event_ids,
            event_count         = len(event_ids),
            model_id            = settings.gemini_model,
            generated_at        = now,
            last_updated_at     = now,
        )

    # ── Case 2: event_id already processed ──────────────────────────────────
    if event_id in existing["processed_event_ids"]:
        logger.info(
            f"event_id already processed — skipping | "
            f"person_id={person_id} | event_id={event_id}"
        )
        return SummaryResponse(
            person_id           = person_id,
            status              = "already_processed",
            main_subject        = existing["main_subject"],
            summary_chain       = existing["summary_chain"],
            processed_event_ids = existing["processed_event_ids"],
            event_count         = existing["event_count"],
            model_id            = existing["model_id"],
            generated_at        = existing["generated_at"],
            last_updated_at     = existing["last_updated_at"],
            message             = (
                f"event_id '{event_id}' is already included in the summary."
            ),
        )

    # ── Case 3: New event → full regeneration ───────────────────────────────
    logger.info(
        f"New event_id — regenerating summary | "
        f"person_id={person_id} | event_id={event_id}"
    )

    # Fetch the new event row
    new_event = get_single_event(event_id)
    if new_event is None:
        return SummaryResponse(
            person_id = person_id,
            status    = "failed",
            message   = (
                f"event_id '{event_id}' not found in input Excel."
            ),
        )

    # Fetch all existing events for this patient
    all_events = get_events_for_patient(person_id)

    # Remove new event if it appears in all_events (avoid duplication)
    all_events = [e for e in all_events if e["event_id"] != event_id]

    # Place new event at TOP — it is the most recent
    all_events = [new_event] + all_events

    # Full regeneration
    gemini_output = await generate_summary(all_events)
    event_ids     = [e["event_id"] for e in all_events]
    now           = datetime.utcnow().isoformat()
    summary_chain = format_summary_chain(
        gemini_output.event_summaries, event_ids
    )

    write_summary(
        person_id           = person_id,
        main_subject        = gemini_output.main_subject,
        summary_chain       = summary_chain,
        processed_event_ids = event_ids,
        generated_at        = existing["generated_at"],  # preserve original creation time
    )

    logger.info(
        f"Summary regenerated | person_id={person_id} | "
        f"total_events={len(event_ids)}"
    )

    return SummaryResponse(
        person_id           = person_id,
        status              = "updated",
        main_subject        = gemini_output.main_subject,
        summary_chain       = summary_chain,
        processed_event_ids = event_ids,
        event_count         = len(event_ids),
        model_id            = settings.gemini_model,
        generated_at        = existing["generated_at"],
        last_updated_at     = now,
        message             = f"Summary updated with new event_id '{event_id}'.",
    )


# ── GET existing summary ───────────────────────────────────────────────────────

async def get_summary(person_id: str) -> SummaryResponse:
    """
    Fetch the current stored summary for a patient from output Excel.
    Returns status 'found' or 'not_found'.
    """
    existing = get_existing_summary(person_id)

    if existing is None:
        return SummaryResponse(
            person_id = person_id,
            status    = "not_found",
            message   = f"No summary found for person_id '{person_id}'.",
        )

    return SummaryResponse(
        person_id           = person_id,
        status              = "found",
        main_subject        = existing["main_subject"],
        summary_chain       = existing["summary_chain"],
        processed_event_ids = existing["processed_event_ids"],
        event_count         = existing["event_count"],
        model_id            = existing["model_id"],
        generated_at        = existing["generated_at"],
        last_updated_at     = existing["last_updated_at"],
    )
