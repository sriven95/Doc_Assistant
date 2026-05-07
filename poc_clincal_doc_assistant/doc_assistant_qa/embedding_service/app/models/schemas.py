from pydantic import BaseModel, Field
from typing import Optional


class BulkEmbedRequest(BaseModel):
    """Trigger bulk embedding for all patients."""
    file_path: Optional[str] = Field(
        default=None,
        description="Override input Excel path. Uses INPUT_FILE from .env if not provided.",
    )

    model_config = {"json_schema_extra": {"example": {"file_path": None}}}


class PatientEmbedRequest(BaseModel):
    """Re-embed a single patient (called after summary update)."""
    person_id: str = Field(..., description="Patient identifier to re-embed")

    model_config = {"json_schema_extra": {"example": {"person_id": "P001"}}}


class JobStatusResponse(BaseModel):
    """Bulk embed job progress."""
    job_id: str
    status: str           = Field(description="queued | processing | completed | failed")
    total_patients: int   = 0
    processed: int        = 0
    failed: int           = 0
    message: Optional[str] = None


class PatientEmbedResponse(BaseModel):
    """Response after embedding a single patient."""
    person_id: str
    status: str           = Field(description="embedded | re_embedded | failed")
    chunks_stored: int    = 0
    events_processed: int = 0
    message: Optional[str] = None
