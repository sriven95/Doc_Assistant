import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Allow shared imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.config import settings
from app.core.logging import logger
from app.api.v1.routes.embed import router as embed_router

from shared.gemini_embedder import init_embedder
from shared.qdrant_store import get_client, ensure_collection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    logger.info("=" * 55)
    logger.info("  Embedding Service starting up")
    logger.info(f"  Env        : {settings.app_env}")
    logger.info(f"  Model      : {settings.gemini_embedding_model}")
    logger.info(f"  Qdrant     : {settings.qdrant_host}:{settings.qdrant_port}")
    logger.info(f"  Collection : {settings.qdrant_collection}")
    logger.info(f"  Input file : {settings.input_file}")
    logger.info("=" * 55)

    # Initialise Gemini auth from service account JSON
    init_embedder(
        settings.google_application_credentials,
        settings.gemini_embedding_model,
        settings.gemini_api_key,
    )
    logger.info("Gemini embedder initialised")

    # Ensure Qdrant collection exists
    qdrant = get_client(settings.qdrant_host, settings.qdrant_port)
    ensure_collection(qdrant, settings.qdrant_collection)
    logger.info(f"Qdrant collection ready | {settings.qdrant_collection}")

    yield

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("Embedding service shutting down.")


app = FastAPI(
    title       = "Doc Assistant — Embedding Service",
    description = (
        "Chunks patient clinical notes (plain_scrubbed_text), "
        "embeds using gemini-embedding-001, and stores in Qdrant. "
        "Supports bulk embed and single patient re-embed."
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

app.include_router(embed_router)


@app.get("/health", tags=["Health"])
async def health():
    return JSONResponse({"status": "ok", "service": "embedding_service"})


@app.get("/", tags=["Health"], include_in_schema=False)
async def root():
    return JSONResponse({
        "service" : "Embedding Service",
        "version" : "1.0.0",
        "docs"    : "/docs",
        "status"  : "running",
    })
