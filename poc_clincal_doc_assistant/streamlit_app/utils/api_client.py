import requests
from typing import Optional

BASE_URL = "http://localhost:8000/api/v1"


def generate_summaries(file_path: Optional[str] = None) -> dict:
    """
    Trigger bulk summary generation.
    Returns job response with job_id.
    """
    try:
        payload = {}
        if file_path:
            payload["file_path"] = file_path
        response = requests.post(f"{BASE_URL}/generate-summaries", json=payload, timeout=10)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to FastAPI service. Make sure it is running on port 8000."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_job_status(job_id: str) -> dict:
    """
    Poll bulk job progress.
    """
    try:
        response = requests.get(f"{BASE_URL}/status/{job_id}", timeout=10)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to FastAPI service."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_summary(person_id: str) -> dict:
    """
    Fetch existing summary for a patient.
    """
    try:
        response = requests.get(f"{BASE_URL}/summary/{person_id.strip()}", timeout=10)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to FastAPI service. Make sure it is running on port 8000."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_summary(person_id: str, event_id: str) -> dict:
    """
    Update a patient's summary with a new event.
    """
    try:
        payload = {
            "person_id": person_id.strip(),
            "event_id" : event_id.strip(),
        }
        response = requests.post(f"{BASE_URL}/update-summary", json=payload, timeout=30)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to FastAPI service. Make sure it is running on port 8000."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_service_health() -> bool:
    """
    Check if the summary FastAPI service is reachable (port 8000).
    """
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


# ── AI Layer Service (port 8002) ───────────────────────────────────────────────

AI_BASE_URL = "http://localhost:8002/api/v1"


def check_ai_service_health() -> bool:
    """Check if the AI layer service is reachable (port 8002)."""
    try:
        response = requests.get("http://localhost:8002/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def chat_start(person_id: str) -> dict:
    """
    Open a patient conversation on the AI layer.
    Returns patient summary + session info.
    """
    try:
        response = requests.post(
            f"{AI_BASE_URL}/chat/start",
            json    = {"person_id": person_id.strip()},
            timeout = 30,
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to AI Layer service. Make sure it is running on port 8002."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def chat_ask(person_id: str, question: str) -> dict:
    """
    Ask a question about a patient.
    Returns grounded answer + source citations.
    """
    try:
        response = requests.post(
            f"{AI_BASE_URL}/chat/ask",
            json    = {"person_id": person_id.strip(), "question": question.strip()},
            timeout = 60,
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to AI Layer service. Make sure it is running on port 8002."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def chat_history(person_id: str) -> dict:
    """Fetch current conversation history for a patient."""
    try:
        response = requests.get(
            f"{AI_BASE_URL}/chat/history/{person_id.strip()}",
            timeout = 10,
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to AI Layer service."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def chat_clear_session(person_id: str) -> dict:
    """Clear a patient's session."""
    try:
        response = requests.delete(
            f"{AI_BASE_URL}/chat/session/{person_id.strip()}",
            timeout = 10,
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}
