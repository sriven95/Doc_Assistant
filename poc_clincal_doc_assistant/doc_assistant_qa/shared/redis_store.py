import json
from typing import List, Dict, Optional
import redis as redis_lib


_client: Optional[redis_lib.Redis] = None


def get_client(host: str, port: int) -> redis_lib.Redis:
    """
    Return a singleton Redis client.
    """
    global _client
    if _client is None:
        _client = redis_lib.Redis(
            host=host,
            port=port,
            decode_responses=True,
        )
    return _client


def _session_key(person_id: str) -> str:
    return f"session:{person_id}"


def session_exists(client: redis_lib.Redis, person_id: str) -> bool:
    """
    Check if a session exists and has not expired.
    """
    return client.exists(_session_key(person_id)) == 1


def create_session(
    client: redis_lib.Redis,
    person_id: str,
    ttl_seconds: int,
) -> None:
    """
    Create a new empty session for this patient.
    TTL is set ONCE at creation — does NOT reset on activity.
    """
    key = _session_key(person_id)
    client.set(key, json.dumps([]), ex=ttl_seconds)


def get_history(
    client: redis_lib.Redis,
    person_id: str,
) -> List[Dict]:
    """
    Return the conversation history for this patient.
    Returns empty list if session does not exist.
    """
    key = _session_key(person_id)
    raw = client.get(key)
    if raw is None:
        return []
    return json.loads(raw)


def append_turn(
    client: redis_lib.Redis,
    person_id: str,
    question: str,
    answer: str,
    max_turns: int,
) -> None:
    """
    Append a Q&A turn to the session history.
    Keeps only the last max_turns turns.
    TTL is NOT reset — 15 min from creation is fixed.
    """
    key = _session_key(person_id)
    raw = client.get(key)

    if raw is None:
        # Session expired — do nothing (caller should check first)
        return

    history: List[Dict] = json.loads(raw)

    history.append({"role": "user",      "content": question})
    history.append({"role": "assistant", "content": answer})

    # Keep only last max_turns (each turn = 2 entries)
    max_entries = max_turns * 2
    if len(history) > max_entries:
        history = history[-max_entries:]

    # Preserve the existing TTL — do NOT use ex= here
    ttl = client.ttl(key)
    if ttl > 0:
        client.set(key, json.dumps(history), ex=ttl)
    else:
        client.set(key, json.dumps(history))


def delete_session(client: redis_lib.Redis, person_id: str) -> None:
    """
    Manually delete a session.
    """
    client.delete(_session_key(person_id))


def get_session_ttl(client: redis_lib.Redis, person_id: str) -> int:
    """
    Return remaining TTL in seconds. -2 if key does not exist.
    """
    return client.ttl(_session_key(person_id))


# ── RAG CONTEXT — 3-turn sliding window ───────────────────────────────────────

def _rag_key(person_id: str) -> str:
    return f"rag_context:{person_id}"


def save_rag_context(
    client: redis_lib.Redis,
    person_id: str,
    current_chunks: List[Dict],
    max_turns: int = 3,
    ttl_seconds: int = 900,
) -> None:
    """
    Save the latest RAG retrieval for a patient.
    Keeps a sliding window of the last max_turns retrievals.

    Structure in Redis:
        rag_context:{person_id} = [
            [chunks_turn_1],   ← oldest
            [chunks_turn_2],
            [chunks_turn_3],   ← newest
        ]

    On turn 4: drop turn_1, append turn_4.
    TTL = same as session (15 min), set only when key is new.
    Duplicates kept as-is — no deduplication.
    """
    key = _rag_key(person_id)
    raw = client.get(key)

    if raw is None:
        history = []
    else:
        history = json.loads(raw)

    history.append(current_chunks)

    # Sliding window — keep only last max_turns
    if len(history) > max_turns:
        history = history[-max_turns:]

    # Preserve TTL if key exists — set TTL only on new key
    existing_ttl = client.ttl(key)
    if existing_ttl > 0:
        client.set(key, json.dumps(history), ex=existing_ttl)
    else:
        client.set(key, json.dumps(history), ex=ttl_seconds)


def get_rag_context(
    client: redis_lib.Redis,
    person_id: str,
) -> List[List[Dict]]:
    """
    Return the last N RAG retrievals for a patient.
    Returns list of chunk lists — newest last.
    Returns empty list if no RAG context stored yet.
    """
    key = _rag_key(person_id)
    raw = client.get(key)
    if raw is None:
        return []
    return json.loads(raw)


def delete_rag_context(client: redis_lib.Redis, person_id: str) -> None:
    """Delete RAG context for a patient (used when session is cleared)."""
    client.delete(_rag_key(person_id))
