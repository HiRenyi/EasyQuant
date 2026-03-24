"""Scheduler registry — tracks APScheduler jobs and their execution history."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_scheduler: Any = None
_job_meta: dict[str, dict] = {}  # job_id -> {name, description, schedule}
_job_history: dict[str, dict] = {}  # job_id -> {last_run, last_status, last_error}


def register_scheduler(scheduler: Any) -> None:
    global _scheduler
    _scheduler = scheduler


def get_scheduler() -> Any:
    return _scheduler


def register_job(job_id: str, name: str, description: str, schedule: str) -> None:
    _job_meta[job_id] = {"name": name, "description": description, "schedule": schedule}


def record_job_run(job_id: str, status: str, error: str | None = None) -> None:
    _job_history[job_id] = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "last_status": status,
        "last_error": error,
    }


def get_jobs_info() -> list[dict]:
    """Return combined info for all registered jobs."""
    scheduler = _scheduler
    jobs = []
    for job_id, meta in _job_meta.items():
        info = {
            "id": job_id,
            "name": meta["name"],
            "description": meta["description"],
            "schedule": meta["schedule"],
            "next_run": None,
            **_job_history.get(job_id, {"last_run": None, "last_status": None, "last_error": None}),
        }
        if scheduler:
            ap_job = scheduler.get_job(job_id)
            if ap_job and ap_job.next_run_time:
                info["next_run"] = ap_job.next_run_time.isoformat()
        jobs.append(info)
    return jobs
