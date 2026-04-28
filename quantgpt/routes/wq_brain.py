"""WQ BRAIN API routes — submit expressions to WorldQuant BRAIN for real simulation."""

import logging
import threading
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..models import User
from ..task_store import (
    active_task_count,
    check_rate_limit,
    persist_task_to_db,
    tasks,
    tasks_lock,
    MAX_ACTIVE_TASKS,
)
from ..wq_brain_client import SUBMIT_THRESHOLDS, WQBrainClient, is_configured

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wq-brain", tags=["wq_brain"])


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _fitness_to_grade(fitness: float | None) -> str:
    if fitness is None:
        return "D"
    if fitness >= 1.0:
        return "A"
    if fitness >= 0.5:
        return "B"
    if fitness >= 0.25:
        return "C"
    return "D"


class WQBrainSubmitRequest(BaseModel):
    expression: str = Field(..., description="FASTEXPR factor expression")
    region: str = Field("USA", description="Market region")
    universe: str = Field("TOP3000", description="WQ Universe")
    delay: int = Field(1, ge=0, le=1, description="Signal delay")
    decay: int = Field(0, ge=0, le=20, description="Alpha decay")
    neutralization: str = Field("SUBINDUSTRY", description="Neutralization method")
    truncation: float = Field(0.08, ge=0, le=0.5, description="Weight truncation")
    auto_submit: bool = Field(False, description="Auto-submit if checks pass")
    session_id: str | None = Field(None, description="Session ID")


def _run_wq_brain_task(task_id: str, req: WQBrainSubmitRequest, user_id: str):
    task = tasks.get(task_id)
    if not task:
        return

    try:
        client = WQBrainClient()

        task["status"] = "authenticating"
        if not client.authenticate():
            task["status"] = "failed"
            task["error"] = "WQ BRAIN 认证失败，请检查 WQ_BRAIN_EMAIL/WQ_BRAIN_PASSWORD 配置"
            return

        task["status"] = "simulating"

        def on_progress(pct: int, message: str):
            task["progress"] = pct
            task["progress_message"] = message

        result = client.simulate(
            expression=req.expression,
            region=req.region,
            universe=req.universe,
            delay=req.delay,
            decay=req.decay,
            neutralization=req.neutralization,
            truncation=req.truncation,
            progress_callback=on_progress,
        )

        if not result.get("ok"):
            task["status"] = "failed"
            task["error"] = result.get("error", "WQ BRAIN simulation failed")
            return

        task["status"] = "checking"
        alpha_id = result.get("alpha_id")
        checks = {}
        submittable = False
        if alpha_id:
            checks = client.check_alpha(alpha_id)
            submittable = client.is_submittable(checks)

        submitted = False
        if req.auto_submit and submittable and alpha_id:
            task["status"] = "submitting"
            submit_result = client.submit_alpha(alpha_id)
            submitted = submit_result.get("ok", False)

        client.close()

        is_data = result.get("is", {})
        oos_data = result.get("oos", {})

        sharpe = _safe_float(is_data.get("sharpe"))
        fitness = _safe_float(is_data.get("fitness"))
        returns_val = _safe_float(is_data.get("returns"))
        turnover = _safe_float(is_data.get("turnover"))

        rating = _fitness_to_grade(fitness)

        task["status"] = "completed"
        task["expression"] = req.expression
        task["result"] = {
            "expression": req.expression,
            "alpha_id": alpha_id,
            "is_metrics": is_data,
            "oos_metrics": oos_data,
            "settings": result.get("settings", {}),
            "checks": checks,
            "submittable": submittable,
            "submitted": submitted,
            "simulation_id": result.get("simulation_id"),
            "backtest_summary": {
                "long_short_sharpe": sharpe,
                "wq_fitness": fitness,
                "rank_ic_mean": None,
                "turnover": turnover,
                "wq_rating": rating,
            },
            "wq_brain": {
                "wq_sharpe": sharpe,
                "wq_fitness": fitness,
                "wq_returns": returns_val,
                "wq_turnover": turnover,
                "wq_rating": rating,
                "submittable": submittable,
            },
            "interpretation": {
                "rating": rating,
            },
        }
        logger.info(f"[{task_id}] WQ BRAIN completed: alpha_id={alpha_id} submittable={submittable}")

    except Exception as e:
        logger.error(f"[{task_id}] WQ BRAIN task error: {e}")
        task["status"] = "failed"
        task["error"] = f"WQ BRAIN 提交异常: {e}"
    finally:
        if "completed_at" not in task:
            task["completed_at"] = time.time()
        try:
            persist_task_to_db(task_id, user_id, task)
        except Exception as e:
            logger.error(f"[{task_id}] DB persist error: {e}")


@router.get("/status")
async def wq_brain_status():
    return {
        "configured": is_configured(),
        "thresholds": SUBMIT_THRESHOLDS,
    }


@router.post("/submit", status_code=202)
async def wq_brain_submit(
    req: WQBrainSubmitRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    if not is_configured():
        raise HTTPException(status_code=503, detail="WQ BRAIN 未配置 — 请设置 WQ_BRAIN_EMAIL 和 WQ_BRAIN_PASSWORD")

    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    if active_task_count() >= MAX_ACTIVE_TASKS:
        raise HTTPException(status_code=503, detail="当前任务已满，请稍后再试")

    task_id = uuid.uuid4().hex[:12]
    user_id = str(user.id)

    with tasks_lock:
        tasks[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "session_id": req.session_id,
            "status": "pending",
            "task_type": "wq_brain_submit",
            "cancelled": False,
            "params": req.model_dump(exclude={"session_id"}),
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_wq_brain_task, args=(task_id, req, user_id), daemon=True,
    )
    thread.start()

    return {"task_id": task_id, "status": "pending"}


@router.post("/{task_id}/submit-alpha")
async def submit_alpha_from_task(
    task_id: str,
    user: User = Depends(get_current_user),
):
    if not is_configured():
        raise HTTPException(status_code=503, detail="WQ BRAIN 未配置")

    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    user_id = str(user.id)
    if task.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权操作此任务")

    result = task.get("result", {})
    alpha_id = result.get("alpha_id")
    if not alpha_id:
        raise HTTPException(status_code=400, detail="任务无关联的 alpha_id")

    client = WQBrainClient()
    if not client.authenticate():
        raise HTTPException(status_code=502, detail="WQ BRAIN 认证失败")

    submit_result = client.submit_alpha(alpha_id)
    client.close()

    if submit_result.get("ok"):
        task["result"]["submitted"] = True

    return {
        "alpha_id": alpha_id,
        "submitted": submit_result.get("ok", False),
        "detail": submit_result.get("detail", ""),
    }
