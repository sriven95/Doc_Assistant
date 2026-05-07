from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    All application settings loaded from environment variables / .env file.
    pydantic-settings handles type casting and validation automatically.
    """

    # ── Gemini ─────────────────────────────────
    # gemini_api_key: str
  #  gemini_api_key: str = "AIzaSyA1Z85EZ_WWsuoMRfvKWB-2NT5Oja2tHz0"
    gemini_model: str = "gemini-2.5-flash"
    google_application_credentials: str = r"C:\\Work\\Application\\poc_clincal_doc_assistant\\Gemini Api Key\\Gemini_api_key.json"

    # ── File Paths ─────────────────────────────
    input_file: str  = "data/input/input.xlsx"
    output_file: str = "data/output/output.xlsx"

    # ── Concurrency ────────────────────────────
    max_concurrent_calls: int = 5

    # ── App ────────────────────────────────────
    app_env: str   = "development"
    log_level: str = "INFO"
    app_name: str  = "Doc Assistant Summary Service"
    app_version: str = "1.0.0"

    # ── Input Excel column names ────────────────
    col_event_id: str        = "event_id"
    col_person_id: str       = "person_id"
    col_doc_type: str        = "doc_type"
    col_scrubbed_text: str   = "plain_scrubbed_text"
    col_run_id: str          = "run_id"
    col_model_id: str        = "model_id"
    col_model_processed: str = "model_processed_at"

    # ── Output Excel column names ───────────────
    out_person_id: str       = "person_id"
    out_main_subject: str    = "main_subject"
    out_summary_chain: str   = "summary_chain"
    out_processed_events: str = "processed_event_ids"
    out_event_count: str     = "event_count"
    out_model_id: str        = "model_id"
    out_generated_at: str    = "generated_at"
    out_last_updated_at: str = "last_updated_at"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance.
    lru_cache ensures we only read .env once — not on every request.
    """
    return Settings()


# Single importable instance
settings = get_settings()
