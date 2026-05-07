import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # ── Gemini ─────────────────────────────────────────────────
    google_application_credentials: str = ""
    gemini_api_key: str                 = ""
    gemini_model: str                   = "gemini-2.5-flash"
    gemini_embedding_model: str         = "gemini-embedding-001"

    # ── Qdrant ─────────────────────────────────────────────────
    qdrant_host: str       = "localhost"
    qdrant_port: int       = 6565
    qdrant_collection: str = "patient_clinical_notes"

    # ── Data files ─────────────────────────────────────────────
    input_file: str  = "data/input/input.xlsx"
    output_file: str = "data/output/output.xlsx"

    # ── Chunking ───────────────────────────────────────────────
    chunk_size: int    = 500
    chunk_overlap: int = 50

    # ── App ────────────────────────────────────────────────────
    app_env: str   = "development"
    log_level: str = "INFO"

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
