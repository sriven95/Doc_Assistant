from pydantic import BaseModel, Field
from typing import List, Optional


# ── REQUEST MODELS ─────────────────────────────────────────────────────────────

class GenerateSummariesRequest(BaseModel):
    """Trigger bulk one-time summary generation."""
    file_path: Optional[str] = Field(
        default=None,
        description="Override path to input Excel. Defaults to INPUT_FILE in .env",
    )

    model_config = {"json_schema_extra": {"example": {"file_path": None}}}


class UpdateSummaryRequest(BaseModel):
    """Called when a patient returns with a new event."""
    person_id: str = Field(..., description="Patient identifier")
    event_id: str  = Field(..., description="New event ID to incorporate")

    model_config = {
        "json_schema_extra": {
            "example": {"person_id": "P123", "event_id": "E999"}
        }
    }


# ── RESPONSE MODELS ────────────────────────────────────────────────────────────

class JobStatusResponse(BaseModel):
    """Progress of an async bulk generation job."""
    job_id: str
    status: str         = Field(description="queued | processing | completed | failed")
    total_patients: int = 0
    processed: int      = 0
    failed: int         = 0
    message: Optional[str] = None


class SummaryResponse(BaseModel):
    """Full patient summary — returned by update, get, and create operations."""
    person_id: str
    status: str         = Field(
        description="created | updated | found | already_processed | not_found | failed"
    )
    main_subject: Optional[str]        = None
    summary_chain: Optional[str]       = None
    processed_event_ids: Optional[List[str]] = []
    event_count: Optional[int]         = 0
    model_id: Optional[str]            = None
    generated_at: Optional[str]        = None
    last_updated_at: Optional[str]     = None
    message: Optional[str]             = None


# ── INTERNAL MODELS ────────────────────────────────────────────────────────────

class GeminiSummaryOutput(BaseModel):
    """
    Internal model — structured output expected from Gemini.
    main_subject    : overall patient clinical picture (1 paragraph)
    event_summaries : one summary per event, newest → oldest
    """
    main_subject: str
    event_summaries: List[str]
