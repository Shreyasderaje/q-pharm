"""In-memory job store with progress tracking."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from .config import JOBS_DIR

_LOCK = threading.Lock()
_JOBS: dict[str, "Job"] = {}


@dataclass
class Job:
    id: str
    status: str = "queued"           # queued | running | completed | failed
    stage: str = "Queued"
    stage_key: str = "queued"
    progress: float = 0.0
    error: Optional[str] = None
    result: Optional[dict] = None
    created: datetime = field(default_factory=datetime.utcnow)
    dir: str = ""

    def as_dict(self, include_result: bool = True) -> dict:
        payload = {
            "job_id": self.id,
            "status": self.status,
            "stage": self.stage,
            "stage_key": self.stage_key,
            "progress": round(self.progress, 4),
            "error": self.error,
            "created": self.created.isoformat() + "Z",
        }
        if self.status == "completed" and include_result:
            payload["result"] = self.result
        return payload


def create_job() -> Job:
    job_id = uuid.uuid4().hex[:12]
    job = Job(id=job_id, dir=str(JOBS_DIR / job_id))
    with _LOCK:
        _JOBS[job_id] = job
        _cleanup_expired_locked()
    (JOBS_DIR / job_id).mkdir(parents=True, exist_ok=True)
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _JOBS.get(job_id)


def update(job_id: str, **fields: Any) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)


def _cleanup_expired_locked() -> None:
    cutoff = datetime.utcnow() - timedelta(hours=8)
    stale = [jid for jid, j in _JOBS.items() if j.created < cutoff]
    for jid in stale:
        _JOBS.pop(jid, None)
