from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.core.logging import logger
from app.api.v1.routes.summary import router as summary_router


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Startup  : verify required dirs exist, log config.
    Shutdown : log graceful shutdown.
    """
    # Startup
    os.makedirs(os.path.dirname(settings.output_file), exist_ok=True)
    os.makedirs(os.path.dirname(settings.input_file),  exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"  {settings.app_name}")
    logger.info(f"  Version : {settings.app_version}")
    logger.info(f"  Env     : {settings.app_env}")
    logger.info(f"  Model   : {settings.gemini_model}")
    logger.info(f"  Input   : {settings.input_file}")
    logger.info(f"  Output  : {settings.output_file}")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Service shutting down gracefully.")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = settings.app_name,
    description = (
        "FastAPI async service that reads patient clinical notes from Excel, "
        "generates structured AI summaries using Gemini Flash 2.5, "
        "and supports incremental updates when patients return with new events."
    ),
    version  = settings.app_version,
    lifespan = lifespan,
    docs_url = "/docs",
    redoc_url= "/redoc",
)


# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # Restrict in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────

app.include_router(summary_router)


# ── Health endpoints ───────────────────────────────────────────────────────────

@app.get("/", tags=["Health"], include_in_schema=False)
async def root():
    return JSONResponse({
        "service" : settings.app_name,
        "version" : settings.app_version,
        "model"   : settings.gemini_model,
        "env"     : settings.app_env,
        "docs"    : "/docs",
        "status"  : "running",
    })


@app.get("/health", tags=["Health"])
async def health():
    """
    Health check endpoint.
    Used by Docker, load balancers, and monitoring tools.
    """
    return JSONResponse({"status": "ok", "service": settings.app_name})
