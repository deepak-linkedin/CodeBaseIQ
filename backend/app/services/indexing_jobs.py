from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_active_jobs: dict[tuple[str, str], str] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_key(user_id: str, repository_url: str) -> tuple[str, str]:
    canonical_url = repository_url.strip().lower().removesuffix(".git").rstrip("/")
    return user_id, canonical_url


def create_or_get_job(user_id: str, repository_url: str) -> tuple[str, bool]:
    """Return (job_id, created). Reuse an active job for the same user/repo."""
    key = _job_key(user_id, repository_url)
    with _lock:
        active_id = _active_jobs.get(key)
        if active_id:
            active = _jobs.get(active_id)
            if active and active["status"] in {"queued", "running"}:
                return active_id, False
            _active_jobs.pop(key, None)

        job_id = uuid.uuid4().hex
        _jobs[job_id] = {
            "job_id": job_id,
            "user_id": user_id,
            "repository_url": repository_url,
            "active_key": key,
            "status": "queued",
            "stage": "queued",
            "message": "Waiting to start…",
            "progress": 0,
            "created_at": _now(),
            "updated_at": _now(),
            "result": None,
            "error": None,
        }
        _active_jobs[key] = job_id
        return job_id, True


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    message: str | None = None,
    progress: int | None = None,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        if status is not None:
            job["status"] = status
        if stage is not None:
            job["stage"] = stage
        if message is not None:
            job["message"] = message
        if progress is not None:
            job["progress"] = max(0, min(100, int(progress)))
        if result is not None:
            job["result"] = result
        if error is not None:
            job["error"] = error
        job["updated_at"] = _now()
        if job["status"] in {"completed", "failed", "cancelled"}:
            key = job.get("active_key")
            if key and _active_jobs.get(key) == job_id:
                _active_jobs.pop(key, None)


def get_job(job_id: str, user_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["user_id"] != user_id:
            return None
        return {k: v for k, v in job.items() if k not in {"user_id", "active_key"}}
