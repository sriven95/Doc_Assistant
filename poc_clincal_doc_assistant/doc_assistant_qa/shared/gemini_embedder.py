import asyncio
import os
from typing import List
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import google.generativeai as genai


_embedder_initialised = False


def init_embedder(creds_path: str, embedding_model: str, api_key: str = "") -> None:
    """
    Initialise Gemini embedding.
    Priority:
      1. Service account JSON (if path exists and file is present)
      2. API key fallback (if JSON not found)
    """
    global _embedder_initialised
    if _embedder_initialised:
        return

    if creds_path and os.path.exists(creds_path):
        # ── Use service account JSON ──
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/generative-language"],
        )
        credentials.refresh(Request())
        genai.configure(credentials=credentials)
        print(f"Gemini embedder: authenticated via service account JSON")

    elif api_key:
        # ── Fallback to API key ──
        genai.configure(api_key=api_key)
        print(f"Gemini embedder: authenticated via API key (JSON not found)")

    else:
        raise ValueError(
            "No Gemini credentials found. "
            "Provide GOOGLE_APPLICATION_CREDENTIALS path OR GEMINI_API_KEY in .env"
        )

    _embedder_initialised = True


async def embed_text(text: str, model: str) -> List[float]:
    """
    Embed a single text string using gemini-embedding-001.
    Returns a 768-dimensional vector.
    Runs synchronous SDK in thread pool to not block event loop.
    """
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: genai.embed_content(
            model=model,
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality = 768,
        ),
    )
    return response["embedding"]


async def embed_query(text: str, model: str) -> List[float]:
    """
    Embed a user query (uses RETRIEVAL_QUERY task type for better search).
    Returns a 768-dimensional vector.
    """
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: genai.embed_content(
            model=model,
            content=text,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality = 768,
        ),
    )
    return response["embedding"]
