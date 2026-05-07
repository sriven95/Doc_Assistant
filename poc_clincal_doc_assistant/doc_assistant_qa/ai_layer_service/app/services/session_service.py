import sys
import os
from typing import List, Dict, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from shared.redis_store import (
    get_client,
    session_exists,
    create_session,
    get_history,
    append_turn,
    delete_session,
    get_session_ttl,
)
from app.config import settings
from app.core.logging import logger


def _redis():
    return get_client(settings.redis_host, settings.redis_port)


def get_or_create_session(person_id: str) -> Tuple[bool, List[Dict], int]:
    """
    Check if session exists for patient.
    If YES → return existing history.
    If NO  → create new session with 15 min fixed TTL.

    Returns: (is_new_session, history, ttl_remaining)
    """
    client = _redis()

    if session_exists(client, person_id):
        history = get_history(client, person_id)
        ttl     = get_session_ttl(client, person_id)
        logger.info(
            f"Existing session retrieved | person_id={person_id} | "
            f"turns={len(history)//2} | ttl={ttl}s"
        )
        return False, history, ttl
    else:
        create_session(client, person_id, settings.redis_session_ttl)
        logger.info(
            f"New session created | person_id={person_id} | "
            f"ttl={settings.redis_session_ttl}s"
        )
        return True, [], settings.redis_session_ttl


def save_turn(person_id: str, question: str, answer: str) -> int:
    """
    Append a Q&A turn to the session.
    TTL is NOT reset — 15 min runs from session creation.
    Returns remaining TTL in seconds.
    """
    client = _redis()
    append_turn(client, person_id, question, answer, settings.max_history_turns)
    ttl = get_session_ttl(client, person_id)
    logger.debug(f"Turn saved | person_id={person_id} | ttl_remaining={ttl}s")
    return ttl


def fetch_history(person_id: str) -> Tuple[List[Dict], int, bool]:
    """
    Return session history, remaining TTL, and whether session is active.
    """
    client = _redis()
    active = session_exists(client, person_id)

    if not active:
        return [], 0, False

    history = get_history(client, person_id)
    ttl     = get_session_ttl(client, person_id)
    return history, ttl, True


def clear_session(person_id: str) -> None:
    """Manually delete session."""
    client = _redis()
    delete_session(client, person_id)
    logger.info(f"Session manually cleared | person_id={person_id}")
