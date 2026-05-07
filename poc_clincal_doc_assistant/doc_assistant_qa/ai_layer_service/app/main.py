import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.config import settings
from app.core.logging import logger
from app.api.v1.routes.chat import router as chat_router

from shared.gemini_embedder import init_embedder
from shared.qdrant_store import get_client, ensure_collection
from shared.redis_store import get_client as redis_get_client

from app.services.gemini_service import init_llm


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    logger.info("=" * 55)
    logger.info("  AI Layer Service starting up")
    logger.info(f"  Env        : {settings.app_env}")
    logger.info(f"  LLM        : {settings.gemini_model}")
    logger.info(f"  Embedder   : {settings.gemini_embedding_model}")
    logger.info(f"  Qdrant     : {settings.qdrant_host}:{settings.qdrant_port}")
    logger.info(f"  Redis      : {settings.redis_host}:{settings.redis_port}")
    logger.info(f"  Session TTL: {settings.redis_session_ttl}s (fixed)")
    logger.info(f"  Max turns  : {settings.max_history_turns}")
    logger.info("=" * 55)

    creds = settings.google_application_credentials

    # Initialise Gemini embedder (for question embedding)
    init_embedder(creds, settings.gemini_embedding_model, settings.gemini_api_key)
    logger.info("Gemini embedder initialised")

    # Initialise Gemini LLM (for answer generation)
    init_llm(creds, settings.gemini_api_key)
    logger.info("Gemini LLM initialised")

    # Verify Qdrant connection
    qdrant = get_client(settings.qdrant_host, settings.qdrant_port)
    ensure_collection(qdrant, settings.qdrant_collection)
    logger.info(f"Qdrant connected | {settings.qdrant_collection}")

    # Verify Redis connection
    redis = redis_get_client(settings.redis_host, settings.redis_port)
    redis.ping()
    logger.info("Redis connected")

    # Start background cache eviction task (evicts after 30 min inactivity)
    from app.services.chat_service import start_eviction_task
    start_eviction_task()
    logger.info("Background cache eviction task started (30 min inactivity)")

    yield

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("AI layer service shutting down.")


app = FastAPI(
    title       = "Doc Assistant — AI Layer Service",
    description = (
        "Conversational Q&A service for clinical staff. "
        "Retrieves patient summaries, searches Qdrant for relevant clinical notes, "
        "maintains conversation history in Redis (15 min fixed TTL), "
        "and generates grounded answers using Gemini Flash 2.5."
    ),
    version  = "1.0.0",
    lifespan = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(chat_router)


@app.get("/health", tags=["Health"])
async def health():
    return JSONResponse({"status": "ok", "service": "ai_layer_service"})


@app.get("/", tags=["Health"], include_in_schema=False)
async def root():
    return JSONResponse({
        "service": "AI Layer Service",
        "version": "1.0.0",
        "docs"   : "/docs",
        "status" : "running",
    })
