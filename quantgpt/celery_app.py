"""Celery application for distributed task execution.

Start worker:
    celery -A quantgpt.celery_app worker --loglevel=info --concurrency=4

Requires: pip install 'quantgpt[celery]'
Configure via env:
    CELERY_BROKER_URL       (default: redis://localhost:6379/0)
    CELERY_RESULT_BACKEND   (default: redis://localhost:6379/0)
"""

from __future__ import annotations

import importlib
import os

from celery import Celery

broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "quantgpt",
    broker=broker,
    backend=backend,
)

celery_app.conf.update(
    task_serializer="pickle",
    result_serializer="pickle",
    accept_content=["pickle", "json"],
    task_track_started=True,
    task_time_limit=900,
    task_soft_time_limit=600,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

ALLOWED_TASKS = {
    "quantgpt.task_executor._run_backtest_in_process",
    "quantgpt.task_executor._run_backtest_precomputed_in_process",
}


@celery_app.task(name="quantgpt.run_cpu_work", bind=True)
def run_cpu_work(self, fn_path: str, args: tuple, kwargs: dict):
    """Dispatch CPU work by allowlisted function path."""
    if fn_path not in ALLOWED_TASKS:
        raise ValueError(f"Blocked task function: {fn_path}")
    module_path, fn_name = fn_path.rsplit(".", 1)
    mod = importlib.import_module(module_path)
    fn = getattr(mod, fn_name)
    return fn(*args, **kwargs)
