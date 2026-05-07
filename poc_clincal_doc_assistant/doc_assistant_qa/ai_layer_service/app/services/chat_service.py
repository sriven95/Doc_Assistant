import sys
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from shared.excel_reader import get_patient_summary
from shared.gemini_embedder import embed_query
from shared.qdrant_store import (
    get_client as qdrant_client,
    search_patient_vectors,
    get_client as get_qdrant_client,
)
from shared.redis_store import (
    get_client as redis_get_client,
    save_rag_context,
    get_rag_context,
    delete_rag_context,
)

from app.config import settings
from app.core.logging import logger
from app.models.schemas import (
    ChatStartResponse,
    AskResponse,
    HistoryResponse,
    SummaryBlock,
    SourceChunk,
)
from app.services.session_service import (
    get_or_create_session,
    save_turn,
    fetch_history,
    clear_session,
)
from app.services.gemini_service import generate_answer
from app.utils.prompt_builder import build_qa_prompt


# ── In-Memory Vector Cache ─────────────────────────────────────────────────────
# Per-patient cache loaded on first chat/start or chat/ask
# Evicted after 30 min of no activity
# Structure:
#   _vector_cache = {
#       "P001": {
#           "chunks"       : [{text, vector, event_id, doc_type}, ...],
#           "loaded_at"    : datetime,
#           "last_accessed": datetime,
#       }
#   }

_vector_cache: Dict[str, Dict] = {}
_CACHE_EVICT_MINUTES = 30
_eviction_task_running = False


def _load_patient_to_cache(person_id: str) -> List[Dict]:
    """
    Load ALL vectors for a patient from Qdrant into in-memory cache.
    Returns list of chunk dicts: {text, vector, event_id, doc_type}
    Called on first access OR after eviction.
    """
    from shared.qdrant_store import get_client, ensure_collection
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    qdrant = get_client(settings.qdrant_host, settings.qdrant_port)

    # Scroll all vectors for this patient — no limit
    all_chunks = []
    offset     = None

    while True:
        results, next_offset = qdrant.scroll(
            collection_name = settings.qdrant_collection,
            scroll_filter   = Filter(
                must=[
                    FieldCondition(
                        key   = "person_id",
                        match = MatchValue(value=person_id),
                    )
                ]
            ),
            limit           = 100,
            offset          = offset,
            with_vectors    = True,
            with_payload    = True,
        )

        for point in results:
            all_chunks.append({
                "id"         : str(point.id),
                "vector"     : point.vector,
                "text"       : point.payload.get("text", ""),
                "event_id"   : point.payload.get("event_id", ""),
                "doc_type"   : point.payload.get("doc_type", ""),
                "chunk_index": point.payload.get("chunk_index", 0),
            })

        if next_offset is None:
            break
        offset = next_offset

    _vector_cache[person_id] = {
        "chunks"       : all_chunks,
        "loaded_at"    : datetime.utcnow(),
        "last_accessed": datetime.utcnow(),
    }

    logger.info(
        f"Patient loaded into memory cache | "
        f"person_id={person_id} | chunks={len(all_chunks)}"
    )
    return all_chunks


def _search_in_memory(
    person_id: str,
    query_vector: List[float],
    top_k: int = 5,
) -> List[Dict]:
    """
    Cosine similarity search within the in-memory cache for a patient.
    Updates last_accessed timestamp.
    Returns top_k most relevant chunks.
    """
    import math

    cache_entry = _vector_cache.get(person_id)
    if not cache_entry:
        return []

    # Update last accessed
    _vector_cache[person_id]["last_accessed"] = datetime.utcnow()

    chunks = cache_entry["chunks"]
    if not chunks:
        return []

    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        dot   = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    scored = [
        {
            "text"    : c["text"],
            "event_id": c["event_id"],
            "doc_type": c["doc_type"],
            "score"   : round(cosine_similarity(query_vector, c["vector"]), 4),
        }
        for c in chunks
        if c.get("vector")
    ]

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _get_or_load_cache(person_id: str) -> List[Dict]:
    """
    Return in-memory cache for patient.
    If not cached or evicted — silently reload from Qdrant.
    Transparent to the caller.
    """
    if person_id not in _vector_cache:
        logger.info(
            f"Cache miss — loading from Qdrant | person_id={person_id}"
        )
        return _load_patient_to_cache(person_id)

    # Update last accessed
    _vector_cache[person_id]["last_accessed"] = datetime.utcnow()
    chunks = _vector_cache[person_id]["chunks"]
    logger.debug(
        f"Cache hit | person_id={person_id} | chunks={len(chunks)}"
    )
    return chunks


async def run_cache_eviction_loop() -> None:
    """
    Background task — runs every 5 minutes.
    Evicts any patient whose last_accessed > 30 minutes ago.
    """
    global _eviction_task_running
    _eviction_task_running = True
    logger.info("Cache eviction background task started")

    while True:
        await asyncio.sleep(300)  # run every 5 min
        now      = datetime.utcnow()
        evict_at = now - timedelta(minutes=_CACHE_EVICT_MINUTES)
        evicted  = []

        for person_id, entry in list(_vector_cache.items()):
            if entry["last_accessed"] < evict_at:
                del _vector_cache[person_id]
                evicted.append(person_id)

        if evicted:
            logger.info(
                f"Cache eviction | evicted={evicted} | "
                f"remaining={list(_vector_cache.keys())}"
            )


def start_eviction_task() -> None:
    """
    Schedule the background eviction loop.
    Called once from main.py lifespan startup.
    """
    global _eviction_task_running
    if not _eviction_task_running:
        asyncio.create_task(run_cache_eviction_loop())
        logger.info("Cache eviction task scheduled")


# ── CHAT START ─────────────────────────────────────────────────────────────────

async def start_chat(person_id: str) -> ChatStartResponse:
    """
    1. Pull latest summary from output Excel → display to user.
    2. Pre-load patient vectors into in-memory cache.
    3. Get or create Redis session (15 min fixed TTL).
    """
    logger.info(f"Chat start | person_id={person_id}")

    # Pull summary
    summary_data = get_patient_summary(person_id, settings.output_file)
    if not summary_data:
        logger.warning(f"No summary found | person_id={person_id}")
        return ChatStartResponse(
            person_id = person_id,
            status    = "no_summary",
            message   = (
                f"No summary found for patient '{person_id}'. "
                "Please run the summary generation service first."
            ),
        )

    summary_block = SummaryBlock(
        person_id       = summary_data["person_id"],
        main_subject    = summary_data["main_subject"],
        summary_chain   = summary_data["summary_chain"],
        event_count     = summary_data["event_count"],
        generated_at    = summary_data["generated_at"],
        last_updated_at = summary_data["last_updated_at"],
    )

    # Pre-load vectors into memory cache (non-blocking via executor)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _get_or_load_cache, person_id)

    # Session
    is_new, history, ttl = get_or_create_session(person_id)
    status = "new_session" if is_new else "existing_session"
    turns  = len(history) // 2

    logger.info(
        f"Session | person_id={person_id} | "
        f"status={status} | turns={turns} | ttl={ttl}s"
    )

    return ChatStartResponse(
        person_id       = person_id,
        status          = status,
        summary         = summary_block,
        session_ttl_sec = ttl,
        history_turns   = turns,
        message         = (
            "New session started. You have 15 minutes."
            if is_new else
            f"Existing session resumed. {turns} previous turns available."
        ),
    )


# ── ASK QUESTION ───────────────────────────────────────────────────────────────

async def ask_question(person_id: str, question: str) -> AskResponse:
    """
    Full Q&A orchestration:
    1.  Embed the question (gemini-embedding-001)
    2.  Search in-memory vector cache (load from Qdrant if evicted — transparent)
    3.  Save current RAG chunks to Redis 3-turn sliding window
    4.  Fetch previous RAG turns (up to 2 historical turns)
    5.  Fetch conversation history from Redis (last 20 turns)
    6.  Build prompt: current RAG + previous RAG + conversation + question
    7.  Call Gemini Flash 2.5 for grounded answer
    8.  Save Q&A turn to Redis
    9.  Return answer with sources
    """
    logger.info(f"Question | person_id={person_id} | q={question[:60]}")

    # Step 1 — Embed question
    query_vector = await embed_query(question, settings.gemini_embedding_model)

    # Step 2 — Search in-memory cache (silently reloads from Qdrant if evicted)
    loop       = asyncio.get_event_loop()
    cache_data = await loop.run_in_executor(None, _get_or_load_cache, person_id)

    if not cache_data:
        logger.warning(f"No vectors in cache or Qdrant | person_id={person_id}")
        return AskResponse(
            person_id = person_id,
            question  = question,
            answer    = (
                "No clinical notes have been embedded for this patient yet. "
                "Please run the embedding service first."
            ),
            sources = [],
            message = "No vectors found for this patient.",
        )

    current_chunks = _search_in_memory(person_id, query_vector, top_k=5)

    # Step 3 — Save current RAG chunks to Redis sliding window
    redis = redis_get_client(settings.redis_host, settings.redis_port)
    save_rag_context(
        client         = redis,
        person_id      = person_id,
        current_chunks = current_chunks,
        max_turns      = 3,
        ttl_seconds    = settings.redis_session_ttl,
    )

    # Step 4 — Fetch previous RAG turns (all stored turns minus the one just saved)
    all_rag_turns = get_rag_context(redis, person_id)
    # Last entry is what we just saved (current turn) — history is everything before
    rag_history   = all_rag_turns[:-1] if len(all_rag_turns) > 1 else []

    # Step 5 — Fetch conversation history
    history, ttl, active = fetch_history(person_id)

    if not active:
        get_or_create_session(person_id)
        history = []
        ttl     = settings.redis_session_ttl
        logger.info(f"Session expired — new session created | person_id={person_id}")

    # After — fetch summary and pass main_subject
    summary_data = get_patient_summary(person_id, settings.output_file)
    main_subject = summary_data.get("main_subject", "") if summary_data else ""

    # Step 6 — Build prompt with current RAG + previous RAG history + conversation
    prompt = build_qa_prompt(
        question       = question,
        context_chunks = current_chunks,
        history        = history,
        rag_history    = rag_history,
        main_subject   = main_subject,
    )

    # Step 7 — Call Gemini Flash 2.5
    answer = await generate_answer(prompt)

    # Step 8 — Save Q&A turn to Redis
    ttl = save_turn(person_id, question, answer)

    # Step 9 — Build response
    sources = [
        SourceChunk(
            event_id = c["event_id"],
            doc_type = c["doc_type"],
            text     = c["text"],
            score    = c["score"],
        )
        for c in current_chunks
    ]

    updated_history, _, _ = fetch_history(person_id)
    turns = len(updated_history) // 2

    logger.info(
        f"Answer generated | person_id={person_id} | "
        f"sources={len(sources)} | rag_history_turns={len(rag_history)} | turns={turns}"
    )

    return AskResponse(
        person_id       = person_id,
        question        = question,
        answer          = answer,
        sources         = sources,
        history_turns   = turns,
        session_ttl_sec = ttl,
    )


# ── GET HISTORY ────────────────────────────────────────────────────────────────

async def get_chat_history(person_id: str) -> HistoryResponse:
    """Return the current conversation history for a patient."""
    history, ttl, active = fetch_history(person_id)
    turns = len(history) // 2

    return HistoryResponse(
        person_id       = person_id,
        history         = history,
        turns           = turns,
        session_ttl_sec = ttl,
        session_active  = active,
    )


# ── DELETE SESSION ─────────────────────────────────────────────────────────────

async def delete_chat_session(person_id: str) -> dict:
    """
    Manually clear a patient's session.
    Also clears RAG context from Redis and evicts from memory cache.
    """
    clear_session(person_id)

    # Clear RAG context from Redis
    redis = redis_get_client(settings.redis_host, settings.redis_port)
    delete_rag_context(redis, person_id)

    # Evict from memory cache
    if person_id in _vector_cache:
        del _vector_cache[person_id]
        logger.info(f"Evicted from memory cache | person_id={person_id}")

    return {
        "person_id": person_id,
        "status"   : "cleared",
        "message"  : (
            f"Session, RAG context, and memory cache for "
            f"patient '{person_id}' have been cleared."
        ),
    }
