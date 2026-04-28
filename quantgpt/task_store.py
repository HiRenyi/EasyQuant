"""In-memory task store, rate limiter, and shared helpers for API workers."""

import asyncio
import logging
import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from .models import Report as ReportModel
from .models import Session as SessionModel
from .models import Task as TaskModel

logger = logging.getLogger(__name__)

# ---- Configuration ----

MAX_ACTIVE_TASKS = int(os.environ.get("QUANTGPT_MAX_ACTIVE_TASKS", "100"))
MAX_TOTAL_TASKS = int(os.environ.get("QUANTGPT_MAX_TOTAL_TASKS", "10000"))
TASK_TTL_SECONDS = int(os.environ.get("QUANTGPT_TASK_TTL", "3600"))
TASK_TIMEOUT_SECONDS = int(os.environ.get("QUANTGPT_TASK_TIMEOUT", "600"))
SSE_TIMEOUT_SECONDS = int(os.environ.get("QUANTGPT_SSE_TIMEOUT", "300"))
MAX_SSE_CONNECTIONS = int(os.environ.get("QUANTGPT_MAX_SSE", "1000"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("QUANTGPT_RATE_LIMIT", "50"))
MAX_PROMPT_LENGTH = int(os.environ.get("QUANTGPT_MAX_PROMPT_LEN", "500"))
MAX_REPORT_FILES = int(os.environ.get("QUANTGPT_MAX_REPORTS", "200"))
MAX_DATE_RANGE_YEARS = 10

# ---- Rate limiter (in-memory, per IP) ----

_rate_buckets: dict[str, list[float]] = defaultdict(list)
_rate_lock = threading.Lock()


def check_rate_limit(ip: str) -> bool:
    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_buckets[ip]
        _rate_buckets[ip] = bucket = [t for t in bucket if now - t < 60]
        if len(bucket) >= RATE_LIMIT_PER_MINUTE:
            return False
        bucket.append(now)
        return True


# ---- Task store (in-memory, bounded) ----

tasks: dict[str, dict] = {}
tasks_lock = threading.Lock()
active_sse_count = 0
sse_lock = threading.Lock()

main_loop: asyncio.AbstractEventLoop | None = None


def active_task_count() -> int:
    return sum(
        1 for t in tasks.values()
        if t.get("status") not in ("completed", "failed", "cancelled", "iteration_completed")
    )


class CancelledException(Exception):
    pass


def check_cancelled(task_id: str):
    task = tasks.get(task_id)
    if task and task.get("cancelled"):
        raise CancelledException()


def cleanup_tasks():
    now = time.time()
    with tasks_lock:
        expired = [
            tid for tid, t in tasks.items()
            if now - t.get("created_at", now) > TASK_TTL_SECONDS
            and t.get("status") in ("completed", "failed", "iteration_completed")
        ]
        for tid in expired:
            tasks.pop(tid, None)


def cleanup_reports(user_id: str | None = None):
    if user_id:
        report_dir = Path(__file__).resolve().parent.parent / "reports" / user_id
    else:
        report_dir = Path(__file__).resolve().parent.parent / "reports"
    if not report_dir.is_dir():
        return
    files = sorted(report_dir.glob("backtest_report_*.html"), key=lambda f: f.stat().st_mtime)
    if len(files) > MAX_REPORT_FILES:
        for f in files[:len(files) - MAX_REPORT_FILES]:
            try:
                f.unlink()
            except OSError:
                pass


def sanitize_task_response(task_dict: dict) -> dict:
    if not isinstance(task_dict, dict):
        return task_dict
    ca = task_dict.get("created_at")
    if isinstance(ca, (int, float)):
        task_dict["created_at"] = datetime.fromtimestamp(ca, tz=timezone.utc).isoformat()
    return task_dict


# ---- DB persistence helpers ----

REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
SAFE_FILENAME_RE = re.compile(r"^backtest_report_[\w]+\.html$")


def persist_task_to_db(task_id: str, user_id: str, task_data: dict, report_filename: str | None = None):
    from .db import _get_session_factory

    async def _do_persist():
        factory = _get_session_factory()
        async with factory() as session:
            try:
                session_id = task_data.get("session_id")
                task_record = TaskModel(
                    id=task_id,
                    user_id=user_id,
                    session_id=session_id,
                    status=task_data.get("status", "failed"),
                    task_type=task_data.get("task_type", "backtest"),
                    params=task_data.get("params"),
                    expression=task_data.get("expression"),
                    result=task_data.get("result"),
                    error=task_data.get("error"),
                )
                await session.merge(task_record)

                if report_filename:
                    report_record = ReportModel(
                        user_id=user_id,
                        task_id=task_id,
                        filename=report_filename,
                    )
                    session.add(report_record)

                if session_id:
                    result = await session.execute(
                        select(SessionModel).where(SessionModel.id == session_id)
                    )
                    sess_record = result.scalar_one_or_none()
                    if sess_record and not sess_record.name:
                        prompt = (task_data.get("params") or {}).get("prompt", "")
                        if prompt:
                            sess_record.name = prompt[:30]

                await session.commit()
                logger.info(f"[{task_id}] persisted to DB")
            except Exception as e:
                await session.rollback()
                logger.error(f"[{task_id}] DB persist failed: {e}")

    if main_loop and main_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(_do_persist(), main_loop)
        try:
            future.result(timeout=30)
        except Exception as e:
            logger.error(f"[{task_id}] DB persist error: {e}")
    else:
        logger.error(f"[{task_id}] main event loop not available for DB persist")


def persist_report_to_db(task_id: str, user_id: str, report_filename: str):
    from .db import _get_session_factory

    async def _do():
        factory = _get_session_factory()
        async with factory() as session:
            try:
                report_record = ReportModel(
                    user_id=user_id,
                    task_id=task_id,
                    filename=report_filename,
                )
                session.add(report_record)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Report persist failed: {e}")

    if main_loop and main_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(_do(), main_loop)
        try:
            future.result(timeout=30)
        except Exception as e:
            logger.error(f"Report persist error: {e}")
    else:
        logger.error("main event loop not available for report persist")
