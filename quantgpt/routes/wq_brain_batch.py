"""WQ BRAIN batch operations — param sweep, batch submit by ID, batch status check."""

import itertools
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
from ..wq_brain_client import get_client, is_configured

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wq-brain", tags=["wq_brain_batch"])

VALID_REGIONS = {"USA", "CHN"}
VALID_UNIVERSES = {"TOP3000", "TOP1000", "TOP500", "TOP200"}
VALID_NEUTRALIZATIONS = {"MARKET", "SUBINDUSTRY", "INDUSTRY", "SECTOR", "NONE"}
MAX_COMBINATIONS = 36
MAX_BATCH_SUBMIT = 50


class WQBrainBatchRequest(BaseModel):
    expression: str = Field(..., description="FASTEXPR factor expression")
    regions: list[str] = Field(default=["USA"], description="Regions to sweep")
    delays: list[int] = Field(default=[1], description="Delays to sweep")
    universes: list[str] = Field(default=["TOP3000"], description="Universes to sweep")
    neutralizations: list[str] = Field(default=["SUBINDUSTRY"], description="Neutralizations to sweep")
    decay: int = Field(0, ge=0, le=20, description="Alpha decay (shared)")
    truncation: float = Field(0.08, ge=0, le=0.5, description="Weight truncation (shared)")
    auto_submit: bool = Field(False, description="Auto-submit if all IS checks pass")
    account: str = Field("primary", description="WQ account: 'primary' or 'alt'")
    session_id: str | None = Field(None, description="Session ID")


class BatchSubmitByIdRequest(BaseModel):
    alpha_ids: list[str] = Field(..., min_length=1, max_length=MAX_BATCH_SUBMIT, description="Alpha IDs to submit")
    account: str = Field("primary", description="WQ account (must be 'primary' for submission)")


class BatchAlphaStatusRequest(BaseModel):
    alpha_ids: list[str] = Field(..., min_length=1, max_length=100, description="Alpha IDs to check")


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _run_batch_task(task_id: str, req: WQBrainBatchRequest, user_id: str):
    task = tasks.get(task_id)
    if not task:
        return

    combos = list(itertools.product(req.regions, req.delays, req.universes, req.neutralizations))
    task["total_combinations"] = len(combos)
    task["completed_combinations"] = 0
    task["sub_results"] = {}

    try:
        account = req.account if req.account in ("primary", "alt") else "primary"
        client = get_client(account)
        task["status"] = "authenticating"
        if not client.authenticate():
            task["status"] = "failed"
            task["error"] = f"WQ BRAIN 认证失败 (account={account})"
            return

        task["status"] = "running"
        best_fitness = -999
        best_key = None
        submittable_count = 0

        for i, (region, delay, universe, neut) in enumerate(combos):
            if task.get("cancelled"):
                task["status"] = "cancelled"
                break

            key = f"{region}_D{delay}_{universe}_{neut}"
            task["progress_message"] = f"[{i+1}/{len(combos)}] {key}"

            result = client.simulate(
                expression=req.expression,
                region=region,
                universe=universe,
                delay=delay,
                decay=req.decay,
                neutralization=neut,
                truncation=req.truncation,
            )

            sub = {"key": key, "region": region, "delay": delay, "universe": universe, "neutralization": neut}

            if not result.get("ok"):
                sub["status"] = "failed"
                sub["error"] = result.get("error", "unknown")
            else:
                alpha_id = result.get("alpha_id")
                is_data = result.get("is", {})

                sharpe = _safe_float(is_data.get("sharpe"))
                fitness = _safe_float(is_data.get("fitness"))
                returns_val = _safe_float(is_data.get("returns"))
                turnover = _safe_float(is_data.get("turnover"))
                rating = "A" if (fitness or 0) >= 1.0 else ("B" if (fitness or 0) >= 0.5 else "C")

                submitted = False
                if req.auto_submit and alpha_id and rating == "A":
                    submit_result = client.submit_alpha(alpha_id)
                    submitted = submit_result.get("ok", False)

                if submitted and alpha_id:
                    try:
                        from ..alpha_tracker import record_submitted_alpha_sync
                        record_submitted_alpha_sync(
                            user_id=user_id, alpha_id=alpha_id, expression=req.expression,
                            region=region, universe=universe, delay=delay,
                            decay=req.decay, neutralization=neut,
                            truncation=req.truncation, sharpe=sharpe, fitness=fitness,
                            returns=returns_val, turnover=turnover,
                        )
                    except Exception as e:
                        logger.warning(f"[{task_id}] alpha tracking failed for {key}: {e}")

                sub["status"] = "completed"
                sub["alpha_id"] = alpha_id
                sub["sharpe"] = sharpe
                sub["fitness"] = fitness
                sub["returns"] = returns_val
                sub["turnover"] = turnover
                sub["submitted"] = submitted

                if rating == "A":
                    submittable_count += 1
                if fitness is not None and fitness > best_fitness:
                    best_fitness = fitness
                    best_key = key

            task["sub_results"][key] = sub
            task["completed_combinations"] = i + 1

        client.close()

        task["status"] = "completed"
        task["result"] = {
            "expression": req.expression,
            "total_combinations": len(combos),
            "completed": task["completed_combinations"],
            "best_fitness": round(best_fitness, 4) if best_fitness > -999 else None,
            "best_key": best_key,
            "submittable_count": submittable_count,
            "sub_results": task["sub_results"],
        }

    except Exception as e:
        logger.error(f"[{task_id}] batch task error: {e}")
        task["status"] = "failed"
        task["error"] = f"批量提交异常: {e}"
    finally:
        if "completed_at" not in task:
            task["completed_at"] = time.time()
        try:
            persist_task_to_db(task_id, user_id, task)
        except Exception as e:
            logger.error(f"[{task_id}] DB persist error: {e}")


@router.post("/batch-submit", status_code=202)
async def wq_brain_batch_submit(
    req: WQBrainBatchRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    if not is_configured():
        raise HTTPException(status_code=503, detail="WQ BRAIN 未配置")

    for r in req.regions:
        if r not in VALID_REGIONS:
            raise HTTPException(status_code=400, detail=f"无效 region: {r}，可选: {sorted(VALID_REGIONS)}")
    for u in req.universes:
        if u not in VALID_UNIVERSES:
            raise HTTPException(status_code=400, detail=f"无效 universe: {u}，可选: {sorted(VALID_UNIVERSES)}")
    for n in req.neutralizations:
        if n not in VALID_NEUTRALIZATIONS:
            raise HTTPException(status_code=400, detail=f"无效 neutralization: {n}，可选: {sorted(VALID_NEUTRALIZATIONS)}")
    for d in req.delays:
        if d not in (0, 1):
            raise HTTPException(status_code=400, detail=f"无效 delay: {d}，可选: 0, 1")

    total = len(req.regions) * len(req.delays) * len(req.universes) * len(req.neutralizations)
    if total > MAX_COMBINATIONS:
        raise HTTPException(status_code=400, detail=f"组合数 {total} 超过上限 {MAX_COMBINATIONS}")

    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁")

    if active_task_count() >= MAX_ACTIVE_TASKS:
        raise HTTPException(status_code=503, detail="当前任务已满")

    task_id = uuid.uuid4().hex[:12]
    user_id = str(user.id)

    with tasks_lock:
        tasks[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "session_id": req.session_id,
            "status": "pending",
            "task_type": "wq_brain_batch",
            "cancelled": False,
            "params": req.model_dump(exclude={"session_id"}),
            "expression": req.expression,
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_batch_task, args=(task_id, req, user_id), daemon=True,
    )
    thread.start()

    return {"task_id": task_id, "status": "pending", "total_combinations": total}


# ---- Batch submit by alpha_id ----


def _run_batch_submit_by_id(task_id: str, alpha_ids: list[str], account: str, user_id: str):
    task = tasks.get(task_id)
    if not task:
        return

    total = len(alpha_ids)
    task["total"] = total
    task["completed"] = 0
    task["sub_results"] = {}

    try:
        client = get_client(account)
        task["status"] = "authenticating"
        if not client.authenticate():
            task["status"] = "failed"
            task["error"] = f"WQ BRAIN 认证失败 (account={account})"
            return

        task["status"] = "running"
        active_count = 0
        sc_fail_count = 0
        timeout_count = 0

        for i, alpha_id in enumerate(alpha_ids):
            if task.get("cancelled"):
                task["status"] = "cancelled"
                break

            task["progress_message"] = f"[{i+1}/{total}] submitting {alpha_id}"

            result = client.submit_alpha(alpha_id)
            platform_status = result.get("platform_status", "")
            sc_value = result.get("sc_value")
            sc_limit = result.get("sc_limit")

            sub = {
                "alpha_id": alpha_id,
                "ok": result.get("ok", False),
                "detail": result.get("detail", ""),
                "platform_status": platform_status,
                "status_code": result.get("status_code"),
            }
            if sc_value is not None:
                sub["sc_value"] = sc_value
                sub["sc_limit"] = sc_limit

            if result.get("ok"):
                active_count += 1
            elif "SC FAIL" in result.get("detail", ""):
                sc_fail_count += 1
            elif platform_status == "TIMEOUT":
                timeout_count += 1

            task["sub_results"][alpha_id] = sub
            task["completed"] = i + 1

        client.close()

        task["status"] = "completed"
        task["result"] = {
            "total": total,
            "completed": task["completed"],
            "active": active_count,
            "sc_fail": sc_fail_count,
            "timeout": timeout_count,
            "sub_results": task["sub_results"],
        }
        logger.info(f"[{task_id}] batch submit done: {active_count} ACTIVE, {sc_fail_count} SC_FAIL, {timeout_count} TIMEOUT")

    except Exception as e:
        logger.error(f"[{task_id}] batch submit error: {e}")
        task["status"] = "failed"
        task["error"] = f"批量提交异常: {e}"
    finally:
        if "completed_at" not in task:
            task["completed_at"] = time.time()
        try:
            persist_task_to_db(task_id, user_id, task)
        except Exception as e:
            logger.error(f"[{task_id}] DB persist error: {e}")


@router.post("/batch-submit-by-id", status_code=202)
async def wq_brain_batch_submit_by_id(
    req: BatchSubmitByIdRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Batch submit multiple already-simulated alphas by their alpha_id.

    Processes sequentially using one authenticated session.
    Returns a task_id for progress polling via GET /tasks/{task_id}.
    """
    if req.account != "primary":
        raise HTTPException(status_code=403, detail="Alpha 提交仅允许 primary 账号")
    if not is_configured(req.account):
        raise HTTPException(status_code=503, detail="WQ BRAIN 未配置")

    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁")

    task_id = uuid.uuid4().hex[:12]
    user_id = str(user.id)

    with tasks_lock:
        tasks[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "status": "pending",
            "task_type": "wq_brain_batch_submit_by_id",
            "cancelled": False,
            "params": {"alpha_ids": req.alpha_ids, "account": req.account},
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_batch_submit_by_id,
        args=(task_id, req.alpha_ids, req.account, user_id),
        daemon=True,
    )
    thread.start()

    return {"task_id": task_id, "status": "pending", "total": len(req.alpha_ids)}


# ---- Batch alpha status check (synchronous) ----


@router.post("/batch-alpha-status")
async def wq_brain_batch_alpha_status(
    req: BatchAlphaStatusRequest,
    user: User = Depends(get_current_user),
    account: str = "primary",
):
    """Check platform status of multiple alphas in one call.

    Returns status, fitness, sharpe, SC check result for each alpha_id.
    """
    if not is_configured(account):
        raise HTTPException(status_code=503, detail=f"WQ BRAIN 未配置 (account={account})")

    client = get_client(account)
    if not client.authenticate():
        raise HTTPException(status_code=502, detail="WQ BRAIN 认证失败")

    results = {}
    for alpha_id in req.alpha_ids:
        data = client.check_alpha_status(alpha_id)
        if not data.get("ok"):
            results[alpha_id] = {"ok": False, "error": data.get("error", "not found")}
            continue

        is_data = data.get("is", {})
        checks = is_data.get("checks", [])
        sc_check = next((c for c in checks if c.get("name") == "SELF_CORRELATION"), None)

        results[alpha_id] = {
            "ok": True,
            "status": data.get("status"),
            "grade": data.get("grade"),
            "sharpe": _safe_float(is_data.get("sharpe")),
            "fitness": _safe_float(is_data.get("fitness")),
            "returns": _safe_float(is_data.get("returns")),
            "turnover": _safe_float(is_data.get("turnover")),
            "sc_result": sc_check.get("result") if sc_check else None,
            "sc_value": sc_check.get("value") if sc_check else None,
            "dateCreated": data.get("dateCreated"),
        }

    client.close()

    summary = {
        "total": len(req.alpha_ids),
        "active": sum(1 for r in results.values() if r.get("status") == "ACTIVE"),
        "unsubmitted": sum(1 for r in results.values() if r.get("status") == "UNSUBMITTED"),
        "sc_fail": sum(1 for r in results.values() if r.get("sc_result") == "FAIL"),
        "sc_pending": sum(1 for r in results.values() if r.get("sc_result") == "PENDING"),
    }

    return {"summary": summary, "alphas": results}
