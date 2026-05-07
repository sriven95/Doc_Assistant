from fastapi import APIRouter, HTTPException, status

from app.models.schemas import (
    GenerateSummariesRequest,
    UpdateSummaryRequest,
    SummaryResponse,
    JobStatusResponse,
)
from app.services.summary_service import (
    start_bulk_job,
    update_patient_summary,
    get_summary,
    get_job_status,
)
from app.core.logging import logger

router = APIRouter(prefix="/api/v1", tags=["Summary Generation"])


# ── POST /api/v1/generate-summaries ───────────────────────────────────────────

@router.post(
    "/generate-summaries",
    response_model=JobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger bulk one-time summary generation",
    description=(
        "Reads the entire input Excel, groups all rows by person_id, "
        "and generates an AI summary for every patient using Gemini Flash 2.5. "
        "Events are processed in natural Excel row order (newest first). "
        "Returns a job_id immediately — poll **/api/v1/status/{job_id}** for progress."
    ),
)
async def generate_summaries(request: GenerateSummariesRequest = None):
    logger.info("Bulk generation endpoint called")
    file_path = request.file_path if request else None
    return start_bulk_job(file_path=file_path)


# ── POST /api/v1/update-summary ───────────────────────────────────────────────

@router.post(
    "/update-summary",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update summary when patient returns with a new event",
    description=(
        "Called when a patient (person_id) returns with a new clinical event (event_id). "
        "Checks if a summary exists and whether the event was already processed. "
        "If the event is new, fetches all events, places the new one at the top "
        "(most recent), and fully regenerates the summary via Gemini Flash 2.5. "
        "Overwrites the patient row in the output Excel."
    ),
)
async def update_summary(request: UpdateSummaryRequest):
    logger.info(
        f"Update summary endpoint called | "
        f"person_id={request.person_id} | event_id={request.event_id}"
    )
    return await update_patient_summary(
        person_id = request.person_id,
        event_id  = request.event_id,
    )


# ── GET /api/v1/summary/{person_id} ───────────────────────────────────────────

@router.get(
    "/summary/{person_id}",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get existing summary for a patient",
    description=(
        "Returns the current stored summary for the given person_id "
        "from the output Excel. "
        "Returns status='not_found' if no summary has been generated yet."
    ),
)
async def get_patient_summary(person_id: str):
    logger.info(f"Get summary endpoint called | person_id={person_id}")
    return await get_summary(person_id)


# ── GET /api/v1/status/{job_id} ───────────────────────────────────────────────

@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Poll bulk job progress",
    description=(
        "Poll this endpoint after calling **/api/v1/generate-summaries** "
        "to check how many patients have been processed. "
        "Status values: queued | processing | completed | failed."
    ),
)
async def job_status(job_id: str):
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return JobStatusResponse(
        job_id         = job["job_id"],
        status         = job["status"],
        total_patients = job.get("total", 0),
        processed      = job.get("processed", 0),
        failed         = job.get("failed", 0),
        message        = job.get("message"),
    )
