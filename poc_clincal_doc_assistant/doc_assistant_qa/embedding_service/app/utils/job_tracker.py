from typing import Dict, Optional


# In-memory job tracker for bulk embedding jobs
# For production: replace with Redis or a database
_jobs: Dict[str, Dict] = {}


def create_job(job_id: str, total: int = 0) -> None:
    _jobs[job_id] = {
        "job_id"    : job_id,
        "status"    : "queued",
        "total"     : total,
        "processed" : 0,
        "failed"    : 0,
        "errors"    : {},
        "message"   : "Job queued.",
    }


def update_job(job_id: str, **kwargs) -> None:
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)


def get_job(job_id: str) -> Optional[Dict]:
    return _jobs.get(job_id)


def increment_processed(job_id: str) -> None:
    if job_id in _jobs:
        _jobs[job_id]["processed"] += 1


def increment_failed(job_id: str, person_id: str, error: str) -> None:
    if job_id in _jobs:
        _jobs[job_id]["failed"] += 1
        _jobs[job_id]["errors"][person_id] = error
