from pydantic import BaseModel, Field
from typing import List, Optional, Dict


# ── REQUEST MODELS ─────────────────────────────────────────────────────────────

class ChatStartRequest(BaseModel):
    """Open a conversation for a patient."""
    person_id: str = Field(..., description="Patient identifier")

    model_config = {"json_schema_extra": {"example": {"person_id": "P001"}}}


class AskRequest(BaseModel):
    """Ask a question about a patient."""
    person_id: str = Field(..., description="Patient identifier")
    question: str  = Field(..., description="Natural language question", max_length=1000)

    model_config = {
        "json_schema_extra": {
            "example": {
                "person_id": "P001",
                "question" : "What SDOH risks does this patient have?",
            }
        }
    }


# ── RESPONSE MODELS ────────────────────────────────────────────────────────────

class SummaryBlock(BaseModel):
    """Patient summary returned on chat start."""
    person_id      : str
    main_subject   : Optional[str] = None
    summary_chain  : Optional[str] = None
    event_count    : int           = 0
    generated_at   : Optional[str] = None
    last_updated_at: Optional[str] = None


class ChatStartResponse(BaseModel):
    """Response when opening a conversation."""
    person_id      : str
    status         : str    = Field(description="new_session | existing_session | no_summary")
    summary        : Optional[SummaryBlock] = None
    session_ttl_sec: int    = 0
    history_turns  : int    = 0
    message        : Optional[str] = None


class SourceChunk(BaseModel):
    """A retrieved context chunk shown as citation."""
    event_id : str
    doc_type : str
    text     : str
    score    : float


class AskResponse(BaseModel):
    """Answer returned after asking a question."""
    person_id     : str
    question      : str
    answer        : str
    sources       : List[SourceChunk] = []
    history_turns : int               = 0
    session_ttl_sec: int              = 0
    message       : Optional[str]     = None


class HistoryResponse(BaseModel):
    """Current session conversation history."""
    person_id      : str
    history        : List[Dict]   = []
    turns          : int          = 0
    session_ttl_sec: int          = 0
    session_active : bool         = False
