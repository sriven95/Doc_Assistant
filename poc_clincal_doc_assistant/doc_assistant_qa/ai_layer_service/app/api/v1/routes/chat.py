from fastapi import APIRouter, HTTPException, status

from app.models.schemas import (
    ChatStartRequest,
    AskRequest,
    ChatStartResponse,
    AskResponse,
    HistoryResponse,
)
from app.services.chat_service import (
    start_chat,
    ask_question,
    get_chat_history,
    delete_chat_session,
)
from app.core.logging import logger

router = APIRouter(prefix="/api/v1/chat", tags=["Chat Q&A"])


# ── POST /api/v1/chat/start ────────────────────────────────────────────────────
@router.post(
    "/start",
    response_model = ChatStartResponse,
    status_code    = status.HTTP_200_OK,
    summary        = "Open a patient conversation",
    description    = (
        "Pulls the latest patient summary from output Excel and displays it. "
        "Creates a new Redis session (15 min fixed TTL) or resumes existing one. "
        "Must be called before /chat/ask."
    ),
)
async def chat_start(request: ChatStartRequest):
    logger.info(f"Chat start endpoint | person_id={request.person_id}")
    return await start_chat(request.person_id)


# ── POST /api/v1/chat/ask ──────────────────────────────────────────────────────
@router.post(
    "/ask",
    response_model = AskResponse,
    status_code    = status.HTTP_200_OK,
    summary        = "Ask a question about a patient",
    description    = (
        "Embeds the question, searches Qdrant for the most relevant clinical note chunks "
        "(strictly scoped to this patient), fetches conversation history from Redis, "
        "builds a grounded prompt, and returns an answer from Gemini Flash 2.5. "
        "Sources are included in the response."
    ),
)
async def chat_ask(request: AskRequest):
    logger.info(
        f"Chat ask endpoint | person_id={request.person_id} | "
        f"question={request.question[:50]}"
    )
    return await ask_question(request.person_id, request.question)


# ── GET /api/v1/chat/history/{person_id} ──────────────────────────────────────
@router.get(
    "/history/{person_id}",
    response_model = HistoryResponse,
    status_code    = status.HTTP_200_OK,
    summary        = "Get conversation history",
    description    = "Returns the current session history and remaining TTL for a patient.",
)
async def chat_history(person_id: str):
    logger.info(f"Chat history endpoint | person_id={person_id}")
    return await get_chat_history(person_id)


# ── DELETE /api/v1/chat/session/{person_id} ───────────────────────────────────
@router.delete(
    "/session/{person_id}",
    status_code = status.HTTP_200_OK,
    summary     = "Clear a patient session",
    description = "Manually delete a patient's Redis session.",
)
async def clear_session(person_id: str):
    logger.info(f"Session clear endpoint | person_id={person_id}")
    return await delete_chat_session(person_id)
