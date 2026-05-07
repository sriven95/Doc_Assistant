
import asyncio
import json
import os
import google.generativeai as genai
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from typing import List, Dict, Tuple

from app.config import settings
from app.models.schemas import GeminiSummaryOutput
from app.utils.prompt_builder import build_prompt
from app.core.logging import logger

def _setup_gemini():
    """
    Authenticate Gemini using service account JSON file directly.
    """
    creds_path = "C:\\Work\\Application\\poc_clincal_doc_assistant\\Gemini Api Key\\Gemini_api_key.json"

    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/generative-language"]
    )
    credentials.refresh(Request())
    genai.configure(credentials=credentials)
    logger.info(f"Gemini authenticated via service account JSON")

_setup_gemini()
_model = genai.GenerativeModel(settings.gemini_model)


async def _call_gemini_async(prompt: str) -> str:
    """
    Make a single async Gemini API call.
    Runs the synchronous SDK in a thread pool executor
    so it does not block the FastAPI event loop.
    """
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _model.generate_content(prompt)
    )
    return response.text.strip()


def _parse_response(raw: str, expected_events: int) -> GeminiSummaryOutput:
    """
    Parse Gemini's raw text response into a GeminiSummaryOutput.

    Handles common issues:
    - Markdown code fences (```json ... ```)
    - Missing or extra event_summaries entries
    - Empty main_subject

    Raises ValueError if JSON is invalid or main_subject is missing.
    """
    cleaned = raw

    # Strip markdown fences if present
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini returned invalid JSON.\nError: {e}\nRaw:\n{raw[:500]}"
        )

    main_subject    = data.get("main_subject", "").strip()
    event_summaries = data.get("event_summaries", [])

    if not main_subject:
        raise ValueError("Gemini response is missing 'main_subject'.")

    # Normalise event_summaries length to match expected number of events
    if len(event_summaries) < expected_events:
        event_summaries += ["Summary not available."] * (
            expected_events - len(event_summaries)
        )
    elif len(event_summaries) > expected_events:
        event_summaries = event_summaries[:expected_events]

    return GeminiSummaryOutput(
        main_subject=main_subject,
        event_summaries=event_summaries,
    )


async def generate_summary(events: List[Dict]) -> GeminiSummaryOutput:
    """
    Generate a full patient summary from a list of events.

    events : ordered newest → oldest
    Returns GeminiSummaryOutput with main_subject + event_summaries list.
    """
    if not events:
        raise ValueError("Cannot generate summary — no events provided.")

    prompt   = build_prompt(events)
    raw      = await _call_gemini_async(prompt)
    logger.debug(f"Gemini response received | length={len(raw)}")

    return _parse_response(raw, expected_events=len(events))


async def generate_summaries_batch(
    patients: Dict[str, List[Dict]],
) -> Tuple[Dict[str, GeminiSummaryOutput], Dict[str, str]]:
    """
    Generate summaries for multiple patients concurrently.

    Uses asyncio.Semaphore to limit parallel Gemini calls
    and avoid hitting API rate limits.

    patients : { person_id: [events list] }
    Returns  : (results dict, errors dict)
               results → { person_id: GeminiSummaryOutput }
               errors  → { person_id: error_message }
    """
    semaphore = asyncio.Semaphore(settings.max_concurrent_calls)
    results: Dict[str, GeminiSummaryOutput] = {}
    errors:  Dict[str, str]                 = {}

    async def _process_one(person_id: str, events: List[Dict]) -> None:
        async with semaphore:
            try:
                output = await generate_summary(events)
                results[person_id] = output
                logger.info(f"Summary generated | person_id={person_id}")
            except Exception as e:
                errors[person_id] = str(e)
                logger.error(f"Summary failed | person_id={person_id} | error={e}")

    tasks = [
        _process_one(pid, evts)
        for pid, evts in patients.items()
    ]
    await asyncio.gather(*tasks)

    logger.info(
        f"Batch complete | success={len(results)} | failed={len(errors)}"
    )
    return results, errors
