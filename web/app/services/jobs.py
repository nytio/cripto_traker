from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)

_JOB_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_running_job() -> dict[str, Any] | None:
    for job in _JOBS.values():
        if job.get("state") == "running":
            return job
    return None


def start_job(
    job_key: str, job_type: str, label: str, target: Callable[[], Any]
) -> dict[str, Any]:
    with _JOB_LOCK:
        running_job = _find_running_job()
        if running_job and running_job.get("job_key") != job_key:
            active_label = running_job.get("label", "Another")
            return {
                "job_key": job_key,
                "job_type": job_type,
                "label": label,
                "state": "busy",
                "message": f"{active_label} update already running.",
                "active_job_key": running_job.get("job_key"),
                "active_job_type": running_job.get("job_type"),
                "active_label": active_label,
            }

        existing = _JOBS.get(job_key)
        if existing and existing.get("state") == "running":
            return existing

        job = {
            "job_key": job_key,
            "job_type": job_type,
            "label": label,
            "state": "running",
            "message": f"{label} update running.",
            "result": None,
            "error": None,
            "started_at": _now_iso(),
            "finished_at": None,
        }
        _JOBS[job_key] = job

    thread = threading.Thread(
        target=_run_job, args=(job_key, target), daemon=True
    )
    thread.start()
    return job


def _run_job(job_key: str, target: Callable[[], Any]) -> None:
    result = None
    error_message = None
    try:
        result = target()
    except Exception as exc:
        error_message = str(exc).strip() or "Update failed."
        logger.exception("Job failed: %s", job_key)

    with _JOB_LOCK:
        job = _JOBS.get(job_key)
        if not job:
            return
        job["finished_at"] = _now_iso()
        if error_message:
            job["state"] = "error"
            job["message"] = error_message
            job["error"] = error_message
            return

        job["state"] = "done"
        job["result"] = result
        if result:
            job["message"] = (
                f"{job.get('label', 'Forecast')} updated: {result} points."
            )
        else:
            job["message"] = f"{job.get('label', 'Forecast')} completed."


def get_job_status(job_key: str, job_type: str, label: str) -> dict[str, Any]:
    with _JOB_LOCK:
        job = _JOBS.get(job_key)
        if not job:
            return {
                "job_key": job_key,
                "job_type": job_type,
                "label": label,
                "state": "idle",
                "message": "",
            }
        return dict(job)
