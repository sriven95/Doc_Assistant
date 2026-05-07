import asyncio
import os
from typing import List, Dict
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import google.generativeai as genai

from app.config import settings
from app.core.logging import logger


_llm_initialised = False
_model = None


def init_llm(creds_path: str, api_key: str = "") -> None:
    """
    Initialise Gemini Flash 2.5.
    Priority:
      1. Service account JSON (if path exists and file is present)
      2. API key fallback (if JSON not found)
    """
    global _llm_initialised, _model

    if _llm_initialised:
        return

    if creds_path and os.path.exists(creds_path):
        # ── Use service account JSON ──
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/generative-language"],
        )
        credentials.refresh(Request())
        genai.configure(credentials=credentials)
        logger.info(f"Gemini LLM: authenticated via service account JSON")

    elif api_key:
        # ── Fallback to API key ──
        genai.configure(api_key=api_key)
        logger.info(f"Gemini LLM: authenticated via API key (JSON not found)")

    else:
        raise ValueError(
            "No Gemini credentials found. "
            "Provide GOOGLE_APPLICATION_CREDENTIALS path OR GEMINI_API_KEY in .env"
        )

    _model           = genai.GenerativeModel(settings.gemini_model)
    _llm_initialised = True
    logger.info(f"Gemini LLM initialised | model={settings.gemini_model}")


async def generate_answer(prompt: str) -> str:
    """
    Call Gemini Flash 2.5 with the full prompt.
    Runs sync SDK in thread pool to not block event loop.
    Returns the answer text.
    """
    if _model is None:
        raise RuntimeError("Gemini LLM not initialised. Call init_llm() first.")

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _model.generate_content(prompt),
    )
    answer = response.text.strip()
    logger.debug(f"Gemini answer generated | length={len(answer)}")
    return answer
