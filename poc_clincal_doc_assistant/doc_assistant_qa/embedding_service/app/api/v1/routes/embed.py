from fastapi import APIRouter, HTTPException, status

from app.models.schemas import (
    BulkEmbedRequest,
    PatientEmbedRequest,
    JobStatusResponse,
    PatientEmbedResponse,
)
from app.services.embed_service import (
    start_bulk_embed_job,
    embed_single_patient,
)
from app.utils.job_tracker import get_job
from app.core.logging import logger

router = APIRouter(prefix="/api/v1/embed", tags=["Embedding"])


# ── POST /api/v1/embed/bulk ────────────────────────────────────────────────────
@router.post(
    "/bulk",
    response_model = JobStatusResponse,
    status_code    = status.HTTP_202_ACCEPTED,
    summary        = "Bulk embed all patients",
    description    = (
        "Reads all patients from input Excel, chunks each event's "
        "plain_scrubbed_text (500 tokens / 50 overlap), embeds using "
        "gemini-embedding-001, and stores in Qdrant. "
        "Returns job_id immediately — poll /embed/status/{job_id} for progress."
    ),
)
async def bulk_embed(request: BulkEmbedRequest = None):
    file_path = request.file_path if request else None
    job_id    = start_bulk_embed_job(file_path)
    logger.info(f"Bulk embed triggered | job_id={job_id}")

    return JobStatusResponse(
        job_id         = job_id,
        status         = "queued",
        total_patients = 0,
        processed      = 0,
        failed         = 0,
        message        = f"Bulk embedding started. Poll /api/v1/embed/status/{job_id}",
    )


# ── POST /api/v1/embed/patient ─────────────────────────────────────────────────
@router.post(
    "/patient",
    response_model = PatientEmbedResponse,
    status_code    = status.HTTP_200_OK,
    summary        = "Embed or re-embed a single patient",
    description    = (
        "Embeds all events for the given person_id. "
        "If vectors already exist in Qdrant, deletes them first then re-embeds. "
        "Called automatically by the summary service when a patient is updated."
    ),
)
async def embed_patient(request: PatientEmbedRequest):
    logger.info(f"Single patient embed triggered | person_id={request.person_id}")
    return await embed_single_patient(request.person_id)


# ── GET /api/v1/embed/status/{job_id} ─────────────────────────────────────────
@router.get(
    "/status/{job_id}",
    response_model = JobStatusResponse,
    status_code    = status.HTTP_200_OK,
    summary        = "Poll bulk embed job progress",
    description    = "Check how many patients have been embedded.",
)
async def embed_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = f"Job '{job_id}' not found.",
        )
    return JobStatusResponse(
        job_id         = job["job_id"],
        status         = job["status"],
        total_patients = job.get("total", 0),
        processed      = job.get("processed", 0),
        failed         = job.get("failed", 0),
        message        = job.get("message"),
    )
