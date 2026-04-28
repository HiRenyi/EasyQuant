"""Strategy backtest routes — JoinQuant Playwright automation.

Endpoint:
    POST /api/v1/strategy-backtest  → Submit a strategy backtest task (async)

The task goes through these phases:
    generating_code → validating_code → logging_in → setting_code →
    configuring_backtest → running_backtest → waiting_completion →
    scraping_results → completed
"""

import asyncio
import logging
import os
import threading
import time
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from ..auth import get_current_user
from ..models import User
from ..schemas import validate_date_format

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["strategy_backtest"])


# ---- Request schema ----

class StrategyBacktestRequest(BaseModel):
    prompt: str = Field(..., description="自然语言策略描述", max_length=2000)
    start_date: str = Field("2023-01-01", description="回测起始日期 YYYY-MM-DD")
    end_date: str = Field("2025-12-31", description="回测结束日期 YYYY-MM-DD")
    initial_capital: float = Field(1_000_000.0, ge=10_000, le=100_000_000, description="初始资金")
    benchmark: str = Field("000300.XSHG", description="基准指数 (JQ格式)")
    session_id: str | None = Field(None, description="会话ID")

    _validate_dates = field_validator("start_date", "end_date")(validate_date_format)


# ---- Endpoint ----

@router.post("/strategy-backtest", status_code=202)
async def strategy_backtest(
    req: StrategyBacktestRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """提交策略回测任务（异步，立即返回 task_id）。"""
    from ..task_store import (  # noqa: I001
        MAX_ACTIVE_TASKS, active_task_count as _active_task_count,
        check_rate_limit as _check_rate_limit, cleanup_tasks as _cleanup_tasks,
        tasks as _tasks, tasks_lock as _tasks_lock,
    )

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    if _active_task_count() >= MAX_ACTIVE_TASKS:
        raise HTTPException(status_code=503, detail="当前任务已满，请稍后再试")

    # Check JQ credentials
    jq_username = os.environ.get("JQ_USERNAME", "")
    jq_password = os.environ.get("JQ_PASSWORD", "")
    if not jq_username or not jq_password:
        raise HTTPException(status_code=500, detail="回测服务未配置，请联系管理员")

    _cleanup_tasks()

    task_id = uuid.uuid4().hex[:12]
    user_id = str(user.id)

    with _tasks_lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "session_id": req.session_id,
            "status": "pending",
            "task_type": "strategy_backtest",
            "params": {
                "prompt": req.prompt,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "initial_capital": req.initial_capital,
                "benchmark": req.benchmark,
                            },
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_strategy_backtest_task,
        args=(task_id, req, user_id),
        daemon=True,
    )
    thread.start()

    return {"task_id": task_id, "status": "pending"}


# ---- Background worker ----

def _run_strategy_backtest_task(
    task_id: str,
    req: StrategyBacktestRequest,
    user_id: str,
):
    """Background thread: LLM code gen → validate → Playwright automation → scrape results."""
    from ..task_store import persist_task_to_db as _persist_task_to_db
    from ..task_store import tasks as _tasks

    task = _tasks.get(task_id)
    if not task:
        return

    try:
        # ---- Phase 1: Generate strategy code via LLM ----
        task["status"] = "generating_code"
        code = _call_deepseek_strategy(req.prompt)
        task["strategy_code"] = code

        # ---- Phase 2: Validate code (AST) ----
        task["status"] = "validating_code"
        from ..strategy_code_utils import validate_strategy_code
        validation = validate_strategy_code(code)
        logger.info(f"[{task_id}] Code validation: valid={validation.valid}, errors={validation.errors}")
        task["validation"] = {
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
        }

        if not validation.valid:
            # Attempt LLM fix (one retry)
            fixed_code = _call_fix_strategy(code, validation.errors, req.prompt)
            if fixed_code:
                validation2 = validate_strategy_code(fixed_code)
                if validation2.valid:
                    code = fixed_code
                    task["strategy_code"] = code
                    task["validation"] = {
                        "valid": True,
                        "errors": [],
                        "warnings": validation2.warnings,
                    }
                else:
                    task["status"] = "failed"
                    task["error"] = f"策略代码无效: {'; '.join(validation2.errors)}"
                    return
            else:
                task["status"] = "failed"
                task["error"] = f"策略代码无效: {'; '.join(validation.errors)}"
                return

        # ---- Phase 3: Run on JoinQuant via Playwright ----
        from ..jq_automation import JQ_BACKTEST_TIMEOUT, JQBacktestConfig, get_jq_service

        jq_config = JQBacktestConfig(
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_capital,
            benchmark=req.benchmark,
            frequency="day",
        )

        def status_callback(status_str: str):
            task["status"] = status_str

        jq_service = get_jq_service()
        logger.info(f"[{task_id}] Scheduling Playwright backtest on main loop...")

        # Schedule async Playwright on the main event loop (where the browser lives)
        from ..task_store import main_loop as _main_loop
        if _main_loop and _main_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                jq_service.run_backtest(code, jq_config, on_status=status_callback),
                _main_loop,
            )
            result = future.result(timeout=JQ_BACKTEST_TIMEOUT + 60)
        else:
            # Fallback: no main loop available (shouldn't happen in production)
            result = asyncio.run(
                jq_service.run_backtest(code, jq_config, on_status=status_callback)
            )

        if not result.success:
            task["status"] = "failed"
            task["error"] = result.error or "策略回测执行失败"
            if result.screenshot_path:
                task["screenshot"] = result.screenshot_path
            return

        # ---- Phase 4: Package results ----
        task["status"] = "completed"
        task["result"] = {
            "metrics": result.metrics,
            "equity_curve": result.equity_curve,
            "trades": result.trades,
            "daily_positions": result.daily_positions,
            "strategy_code": code,
            "params": {
                "prompt": req.prompt,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "initial_capital": req.initial_capital,
                "benchmark": req.benchmark,
                            },
        }
        if result.csv_path:
            task["result"]["csv_path"] = result.csv_path

    except Exception:
        logger.error(f"[{task_id}] strategy backtest failed: {traceback.format_exc()}")
        task["status"] = "failed"
        task["error"] = "策略回测过程中发生内部错误"
    finally:
        if "completed_at" not in task:
            task["completed_at"] = time.time()
        try:
            _persist_task_to_db(task_id, user_id, task)
        except Exception as e:
            logger.error(f"[{task_id}] DB persist error: {e}")


# ---- LLM helpers ----

def _get_strategy_llm_config() -> dict:
    """Get LLM config for strategy generation.

    Priority: STRATEGY_LLM_* > DEEPSEEK_*.
    Returns dict with keys: api_key, base_url, model, provider ('anthropic' or 'openai').
    """
    provider = os.environ.get("STRATEGY_LLM_PROVIDER", "").lower()
    api_key = os.environ.get("STRATEGY_LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    base_url = os.environ.get("STRATEGY_LLM_BASE_URL") or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("STRATEGY_LLM_MODEL") or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    # Auto-detect provider from model name
    if not provider:
        if "claude" in model.lower():
            provider = "anthropic"
        else:
            provider = "openai"

    if not api_key:
        raise ValueError("STRATEGY_LLM_API_KEY 或 DEEPSEEK_API_KEY 未配置")
    return {"api_key": api_key, "base_url": base_url, "model": model, "provider": provider}


def _call_deepseek_strategy(prompt: str, max_retries: int = 2) -> str:
    """Call LLM to generate strategy code from natural language."""
    from ..strategy_code_utils import extract_python_code
    from ..strategy_prompt import STRATEGY_SYSTEM_PROMPT

    cfg = _get_strategy_llm_config()
    logger.info(f"Strategy LLM: provider={cfg['provider']}, model={cfg['model']}, base_url={cfg['base_url'][:40]}")

    last_raw = ""
    for attempt in range(1, max_retries + 1):
        if cfg["provider"] == "anthropic":
            raw = _call_anthropic(cfg, STRATEGY_SYSTEM_PROMPT, prompt)
        else:
            raw = _call_openai(cfg, STRATEGY_SYSTEM_PROMPT, prompt)

        logger.info(f"LLM response (attempt {attempt}): length={len(raw)}, first 200: {raw[:200]}")

        if not raw.strip():
            logger.warning(f"LLM returned empty content (attempt {attempt}/{max_retries})")
            last_raw = raw
            continue

        code = extract_python_code(raw)
        if code:
            return code
        last_raw = raw

    raise ValueError(f"LLM 未返回有效的 Python 代码（已重试{max_retries}次），原始内容前500字: {last_raw[:500]}")


def _call_openai(cfg: dict, system_prompt: str, user_prompt: str) -> str:
    """Call OpenAI-compatible API."""
    from openai import OpenAI
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=4096,
        timeout=120,
    )
    return resp.choices[0].message.content or ""


def _call_anthropic(cfg: dict, system_prompt: str, user_prompt: str) -> str:
    """Call Anthropic-compatible API (Nuoda / official)."""
    import anthropic
    client = anthropic.Anthropic(api_key=cfg["api_key"], base_url=cfg["base_url"])
    resp = client.messages.create(
        model=cfg["model"],
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.3,
    )
    return resp.content[0].text if resp.content else ""


def _call_fix_strategy(code: str, errors: list[str], original_prompt: str) -> str | None:
    """Ask LLM to fix validation errors in the generated code. Returns fixed code or None."""
    from ..strategy_code_utils import extract_python_code
    from ..strategy_prompt import STRATEGY_FIX_PROMPT, STRATEGY_SYSTEM_PROMPT

    cfg = _get_strategy_llm_config()
    fix_prompt = STRATEGY_FIX_PROMPT.format(errors="\n".join(f"- {e}" for e in errors))
    combined_prompt = f"原始需求：{original_prompt}\n\n之前生成的代码：\n```python\n{code}\n```\n\n{fix_prompt}"

    try:
        if cfg["provider"] == "anthropic":
            raw = _call_anthropic(cfg, STRATEGY_SYSTEM_PROMPT, combined_prompt)
        else:
            raw = _call_openai(cfg, STRATEGY_SYSTEM_PROMPT, combined_prompt)
        return extract_python_code(raw)
    except Exception as e:
        logger.warning(f"Strategy fix LLM call failed: {e}")
        return None
