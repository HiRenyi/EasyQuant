"""REST API server for QuantGPT.

Endpoints:
    POST /api/v1/auto_backtest           — 提交回测任务（异步，立即返回 task_id）
    GET  /api/v1/tasks                   — 分页查询当前用户任务列表
    GET  /api/v1/tasks/{task_id}         — 查询任务状态和结果
    GET  /api/v1/tasks/{task_id}/stream  — SSE 实时推送任务状态
    POST /api/v1/tasks/{task_id}/iterate — 提交迭代优化任务
    POST /api/v1/tasks/{task_id}/select_candidate — 选择迭代候选因子
    GET  /api/v1/reports/{filename}      — 下载 HTML 报告
    POST /api/v1/feedback                — 提交问题反馈
    POST /api/v1/auth/send-code          — 发送验证码
    POST /api/v1/auth/verify-code        — 验证码登录/注册
    POST /api/v1/auth/refresh            — 刷新 Token
    GET  /api/v1/auth/me                 — 当前用户信息
    GET  /api/v1/health                  — 健康检查

启动: DEEPSEEK_API_KEY=sk-xxx python -m quantgpt --transport http --port 8002
"""

import asyncio
import base64
import json
import logging
import os
import re
import time
import traceback
import uuid
import threading
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .expression_parser import parse_expression
from .expression_parser import __doc__ as _expr_module_doc
from .market_data import MarketDataFetcher, get_universe, fetch_benchmark_returns
from .backtest import run_factor_backtest
from .report import generate_report
from .iteration import compute_factor_score, generate_iteration_candidates
from .db import get_db, init_db, close_db
from .models import User, Task as TaskModel, Report as ReportModel, Feedback as FeedbackModel, Session as SessionModel
from .auth import get_current_user, decode_token
from .routes.auth import router as auth_router
from .routes.sessions import router as sessions_router
from .routes.admin import router as admin_router

logger = logging.getLogger(__name__)

# ---- Configuration ----

MAX_ACTIVE_TASKS = int(os.environ.get("QUANTGPT_MAX_ACTIVE_TASKS", "5"))
MAX_TOTAL_TASKS = int(os.environ.get("QUANTGPT_MAX_TOTAL_TASKS", "200"))
TASK_TTL_SECONDS = int(os.environ.get("QUANTGPT_TASK_TTL", "3600"))
TASK_TIMEOUT_SECONDS = int(os.environ.get("QUANTGPT_TASK_TIMEOUT", "600"))
SSE_TIMEOUT_SECONDS = int(os.environ.get("QUANTGPT_SSE_TIMEOUT", "300"))
MAX_SSE_CONNECTIONS = int(os.environ.get("QUANTGPT_MAX_SSE", "50"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("QUANTGPT_RATE_LIMIT", "10"))
MAX_PROMPT_LENGTH = int(os.environ.get("QUANTGPT_MAX_PROMPT_LEN", "500"))
MAX_REPORT_FILES = int(os.environ.get("QUANTGPT_MAX_REPORTS", "200"))
MAX_DATE_RANGE_YEARS = 10
VALID_UNIVERSES = {"small_scale", "hs300", "csi500"}
VALID_BENCHMARKS = {"hs300", "zz500", "sz50"}

# ---- Lifespan ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    await init_db()
    logger.info("Database initialized")
    yield
    await close_db()
    _main_loop = None
    logger.info("Database connection closed")

# ---- App ----

_cors_origins = os.environ.get("QUANTGPT_CORS_ORIGINS", "*")
_cors_list = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app = FastAPI(
    title="QuantGPT API",
    version="0.1.0",
    description="QuantGPT — 用自然语言回测 A 股因子",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Register auth routes
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(admin_router)


# ---- Rate limiter (in-memory, per IP) ----

_rate_buckets: dict[str, list[float]] = defaultdict(list)
_rate_lock = threading.Lock()


def _check_rate_limit(ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_buckets[ip]
        # Purge entries older than 60s
        _rate_buckets[ip] = bucket = [t for t in bucket if now - t < 60]
        if len(bucket) >= RATE_LIMIT_PER_MINUTE:
            return False
        bucket.append(now)
        return True


# ---- Task store (in-memory, bounded) ----

_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()
_active_sse_count = 0
_sse_lock = threading.Lock()


def _active_task_count() -> int:
    """Count tasks that are still running (not completed/failed/iteration_completed)."""
    return sum(
        1 for t in _tasks.values()
        if t.get("status") not in ("completed", "failed", "iteration_completed")
    )


def _cleanup_tasks():
    """Remove expired tasks from in-memory store."""
    now = time.time()
    with _tasks_lock:
        expired = [
            tid for tid, t in _tasks.items()
            if now - t.get("created_at", now) > TASK_TTL_SECONDS
            and t.get("status") in ("completed", "failed", "iteration_completed")
        ]
        for tid in expired:
            _tasks.pop(tid, None)


def _cleanup_reports(user_id: str | None = None):
    """Remove oldest report files if over limit."""
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


# ---- Request model ----

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AutoBacktestRequest(BaseModel):
    prompt: str = Field(..., description="自然语言描述", examples=["帮我测试一个20日动量因子"])
    universe: str = Field("hs300", description="股票池: small_scale / hs300 / csi500")
    start_date: str = Field("2023-01-01", description="起始日期 YYYY-MM-DD")
    end_date: str = Field("2025-12-31", description="结束日期 YYYY-MM-DD")
    n_groups: int = Field(5, description="分组数量", ge=2, le=20)
    holding_period: int = Field(5, description="持仓周期(交易日)", ge=1, le=60)
    benchmark: str = Field("hs300", description="基准指数: hs300 / zz500 / sz50")
    session_id: str | None = Field(None, description="关联会话 ID")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("prompt 不能为空")
        if len(v) > MAX_PROMPT_LENGTH:
            raise ValueError(f"prompt 长度不能超过 {MAX_PROMPT_LENGTH} 字符")
        return v

    @field_validator("universe")
    @classmethod
    def validate_universe(cls, v: str) -> str:
        if v not in VALID_UNIVERSES:
            raise ValueError(f"universe 必须是 {VALID_UNIVERSES} 之一")
        return v

    @field_validator("benchmark")
    @classmethod
    def validate_benchmark(cls, v: str) -> str:
        if v not in VALID_BENCHMARKS:
            raise ValueError(f"benchmark 必须是 {VALID_BENCHMARKS} 之一")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        if not _DATE_RE.match(v):
            raise ValueError("日期格式必须为 YYYY-MM-DD")
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"无效日期: {v}")
        return v


# ---- LLM: DeepSeek (OpenAI-compatible) ----

_FACTOR_OPERATORS = """
================================================================================
Factor Expression Syntax (Alpha101+ Extended)
================================================================================

SUPPORTED OPERATORS:

Cross-sectional: rank(expr), zscore(expr), sign(expr), log(expr), abs(expr), scale(expr)
Time-series: ts_mean(col,N), ts_std(col,N), ts_sum(col,N), ts_max(col,N), ts_min(col,N),
  ts_shift(col,N), ts_delta(col,N), ts_rank(col,N), ts_argmax(col,N), ts_argmin(col,N),
  decay_linear(col,N), product(col,N)
Dual-column: ts_corr(col1,col2,N), ts_cov(col1,col2,N)
Nonlinear: power(base,exp), sign_power(base,exp), tanh(expr), sigmoid(expr), exp(expr), sqrt(expr)
Conditional: max(a,b), min(a,b), where(cond,true_val,false_val), clip(expr,lower,upper)
Arithmetic: +, -, *, /, ^ (power)
Comparison: >, <, >=, <=, ==, !=
Logical: and, or (combine conditions in where())
Columns: open, high, low, close, volume, amount, pct_change
Special vars: vwap, adv{N} (e.g. adv20), returns, cap
Aliases: delta=ts_delta, delay=ts_shift, correlation=ts_corr, covariance=ts_cov

================================================================================
SYNTAX RULES:
================================================================================
RULE #1: 每个时序函数需要正确的参数个数
  ts_mean(col, N) — 2 个参数    ts_corr(col1, col2, N) — 3 个参数
  where(cond, true_val, false_val) — 3 个参数
  ✗ ts_shift(expr < 30, 1, ...) ← 错误，ts_shift 只接受 2 个参数

RULE #2: 括号必须严格平衡
  ✓ rank(close / ts_mean(close, 20))
  ✗ rank(close / ts_mean(close, 20) ← 缺少右括号

RULE #3: where() 条件可以用 and/or 组合多个条件
  ✓ where(close > ts_mean(close, 5) and volume > ts_mean(volume, 10), close, 0)
  ✓ where(ts_rank(volume, 20) > 0.7 or ts_delta(close, 5) > 0, 1, 0)

RULE #4: 使用非线性变换捕捉市场动态
  ✓ power(rank(volume/adv20), 2)
  ✓ sign_power(ts_corr(close, volume, 20), 0.5)
  ✓ log(1 + abs(ts_delta(close, 20)/close)) * sign(ts_delta(close, 20))

RULE #5: 组合多种信号类型
  ✓ rank(ts_corr(close, volume, 20)) * rank(ts_delta(close, 10)/close)

================================================================================
EXAMPLES:
================================================================================
动量: rank(close/ts_mean(close, 20))
反转: rank(-1 * ts_delta(close, 5) / ts_shift(close, 5))
波动率: ts_std(close/ts_shift(close, 1) - 1, 20)
量价相关: rank(ts_corr(close, volume, 10))
成交量异动: rank(volume/ts_mean(volume, 10))
非线性动量: sign_power(ts_delta(close, 20)/close, 0.5) * rank(volume/adv20)
条件因子: rank(where(ts_rank(volume,20) > 0.7, ts_delta(close,10)/close, 0)) * rank(volume/adv20)
多头排列: rank(where(close > ts_mean(close, 5) and ts_mean(close, 5) > ts_mean(close, 10), close / ts_mean(close, 20), 0))
衰减加权: decay_linear(rank(ts_corr(vwap, volume, 10)), 5)
复合因子: sign_power(rank(volume/adv20), 2) * rank((close-vwap)/close) * rank(ts_std(returns,20))
裁剪因子: rank(clip(ts_corr(close, volume, 20), -0.5, 0.5)) * sign_power(ts_delta(close,20)/close, 0.5)
================================================================================
"""

_OPERATORS_DOC = _FACTOR_OPERATORS  # backward compat alias

_SYSTEM_PROMPT = """你是一个量化因子表达式生成器。用户会用自然语言描述想要的因子，你需要生成一个合法的因子表达式。

{operators}

================================================================================
⚠️ 关键注意事项
================================================================================
- 🚨 只能使用上面 SUPPORTED OPERATORS 中列出的函数，禁止使用 rsi, macd, ema, sma, bbands, atr, obv, adx 等未列出的技术指标函数
- ts_rank(col, N) 返回百分位排名，范围 0~1（不是 0~100），与之比较时用 0.3 而非 30
- where() 条件会使因子值变成离散值（如 -1, 0, 1），可能导致分组失败，尽量避免使用
- 优先使用连续值因子表达式（如 rank(), zscore(), ts_mean() 等），分组效果更好
- returns 是日收益率（如 0.02 代表 2%），close 是收盘价

================================================================================
🚨 输出格式要求（必须严格遵守）🚨
================================================================================
只返回一个因子表达式，不要任何解释、分析或推理过程。
不要使用 markdown 代码块、反引号或引号包裹。
不要以"根据分析"、"我将"、"改进的因子"等开头。

✅ 正确（你的完整回复）:
rank(volume / ts_mean(volume, 20))

❌ 错误（会导致执行失败）:
根据分析，我建议使用反转因子：
rank((close - ts_mean(close, 60)) / ts_std(close, 60))

你的回复必须是恰好一行可执行的因子表达式，不要任何其他内容。
================================================================================
"""


def _clean_expression(raw: str) -> str:
    """Clean LLM response to extract pure factor expression."""
    text = raw.strip()
    # Remove markdown code blocks
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip("`").strip()
    # If multi-line, extract last line containing factor operators
    if "\n" in text:
        factor_ops = ["rank(", "ts_mean(", "ts_std(", "ts_delta(", "ts_shift(",
                       "ts_corr(", "where(", "sign_power(", "power(", "decay_linear(",
                       "log(", "abs(", "zscore(", "close", "volume"]
        for line in reversed(text.split("\n")):
            line = line.strip()
            if any(op in line for op in factor_ops):
                return line
    return text


def _validate_parentheses(expr: str) -> str | None:
    """Check if parentheses are balanced. Returns error message or None."""
    depth = 0
    for i, ch in enumerate(expr):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0:
                return f"括号不平衡：位置 {i} 处多余的右括号 ')'"
    if depth > 0:
        return f"括号不平衡：缺少 {depth} 个右括号 ')'"
    return None


def _call_deepseek(prompt: str) -> str:
    """Call DeepSeek API to generate factor expression."""
    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    client = OpenAI(api_key=api_key, base_url=base_url)
    operators_doc = _expr_module_doc or _FACTOR_OPERATORS
    system = _SYSTEM_PROMPT.format(operators=operators_doc)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=256,
        timeout=30,
    )
    return _clean_expression(resp.choices[0].message.content)


def _call_fix_expression(expression: str, error: str, prompt: str) -> str:
    """Call LLM to fix a broken factor expression."""
    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    client = OpenAI(api_key=api_key, base_url=base_url)
    operators_doc = _expr_module_doc or _FACTOR_OPERATORS

    system = (
        "你是一个因子表达式修复助手。\n\n"
        f"{operators_doc}\n\n"
        "修复下面的表达式。只返回修正后的表达式，不要任何解释、代码块或引号。"
    )
    user = (
        f"用户需求: {prompt}\n\n"
        f"以下因子表达式执行失败:\n"
        f"`{expression}`\n\n"
        f"错误信息:\n{error}"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        max_tokens=256,
        timeout=30,
    )
    return _clean_expression(resp.choices[0].message.content)


# ---- DB persistence helper ----

# Reference to the main asyncio event loop (set during lifespan startup)
_main_loop: asyncio.AbstractEventLoop | None = None


def _persist_task_to_db(task_id: str, user_id: str, task_data: dict, report_filename: str | None = None):
    """Persist completed/failed task to DB (called from background thread)."""
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
                    params=task_data.get("params"),
                    expression=task_data.get("expression"),
                    result=task_data.get("result"),
                    error=task_data.get("error"),
                )
                session.add(task_record)

                if report_filename:
                    report_record = ReportModel(
                        user_id=user_id,
                        task_id=task_id,
                        filename=report_filename,
                    )
                    session.add(report_record)

                # Auto-name session if it has no name yet
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

    if _main_loop and _main_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(_do_persist(), _main_loop)
        try:
            future.result(timeout=30)
        except Exception as e:
            logger.error(f"[{task_id}] DB persist error: {e}")
    else:
        logger.error(f"[{task_id}] main event loop not available for DB persist")


# ---- Background worker ----

def _run_backtest_task(task_id: str, req: AutoBacktestRequest, user_id: str):
    """Execute backtest in background thread, update task store."""
    task = _tasks.get(task_id)
    if not task:
        return

    report_filename = None
    try:
        # Validate date range
        start = datetime.strptime(req.start_date, "%Y-%m-%d")
        end = datetime.strptime(req.end_date, "%Y-%m-%d")
        if start >= end:
            task["status"] = "failed"
            task["error"] = "开始日期必须早于结束日期"
            return
        if (end - start).days > MAX_DATE_RANGE_YEARS * 365:
            task["status"] = "failed"
            task["error"] = f"日期范围不能超过 {MAX_DATE_RANGE_YEARS} 年"
            return

        # 1. LLM generate expression
        task["status"] = "generating_expression"
        expression = _call_deepseek(req.prompt)
        task["expression"] = expression
        logger.info(f"[{task_id}] expression generated: {expression}")

        # 2. Validate expression (with fix-retry)
        task["status"] = "validating"
        dummy = pd.DataFrame({
            "open": [1.0, 2.0, 3.0], "high": [1.1, 2.1, 3.1],
            "low": [0.9, 1.9, 2.9], "close": [1.0, 2.0, 3.0],
            "volume": [100, 200, 300], "amount": [100, 400, 900],
            "pct_change": [0, 100, 50],
        })

        # 2a. Parentheses pre-check
        paren_err = _validate_parentheses(expression)
        if paren_err:
            logger.warning(f"[{task_id}] parentheses error, attempting fix: {paren_err}")
            expression = _call_fix_expression(expression, paren_err, req.prompt)
            task["expression"] = expression

        # 2b. Parse & smoke-test
        try:
            func = parse_expression(expression)
            func(dummy)
        except Exception as e:
            # Attempt LLM fix (once)
            logger.warning(f"[{task_id}] validation failed, attempting fix: {e}")
            try:
                fixed = _call_fix_expression(expression, str(e), req.prompt)
                func = parse_expression(fixed)
                func(dummy)
                expression = fixed
                task["expression"] = expression
                logger.info(f"[{task_id}] expression fixed: {expression}")
            except Exception as e2:
                task["status"] = "failed"
                task["error"] = f"因子表达式无效: {e2}"
                return

        # 3. Fetch data
        task["status"] = "fetching_data"
        stock_codes = get_universe(req.universe, date=req.start_date)
        fetcher = MarketDataFetcher()
        market_df = fetcher.fetch_stocks(stock_codes, req.start_date, req.end_date)
        if market_df is None or len(market_df) == 0:
            task["status"] = "failed"
            task["error"] = "未获取到行情数据，请检查日期范围"
            return

        # 4. Run backtest
        task["status"] = "backtesting"
        result = run_factor_backtest(market_df, expression, req.n_groups, req.holding_period)

        # 4a. Anti-overfit analysis
        anti_overfit_result = None
        factor_df = result.get("_factor_df")
        if factor_df is not None and len(factor_df) > 100:
            task["status"] = "analyzing"
            try:
                from .anti_overfit import run_anti_overfit
                anti_overfit_result = run_anti_overfit(factor_df, req.holding_period)
            except Exception as e:
                logger.warning(f"[{task_id}] anti-overfit analysis failed: {e}")

        # 5. Generate report (into user-specific directory)
        task["status"] = "generating_report"
        bm_returns = None
        try:
            bm_returns = fetch_benchmark_returns(req.benchmark, req.start_date, req.end_date)
        except Exception:
            logger.warning(f"[{task_id}] benchmark fetch failed")

        user_report_dir = Path(__file__).resolve().parent.parent / "reports" / user_id
        user_report_dir.mkdir(parents=True, exist_ok=True)

        report_result = generate_report(
            result["strategy_returns"],
            benchmark_returns=bm_returns,
            title="Factor Top-Group Backtest",
            output_dir=str(user_report_dir),
        )
        report_filename = Path(report_result["report_path"]).name

        # Done
        task["status"] = "completed"
        task["result"] = {
            "report_url": f"/api/v1/reports/{report_filename}",
            "metrics": report_result["metrics"],
            "backtest_summary": {
                "long_short_sharpe": result["long_short_sharpe"],
                "long_short_annual": result.get("long_short_annual", 0),
                "top_group_sharpe": result.get("top_group_sharpe", 0),
                "monotonicity_score": result["monotonicity_score"],
                "spread": result["spread"],
                "group_returns": result["group_returns"],
                "ic_mean": result.get("ic_mean", 0),
                "rank_ic_mean": result.get("rank_ic_mean", 0),
                "ic_ir": result.get("ic_ir", 0),
                "ic_win_rate": result.get("ic_win_rate", 0),
                "turnover": result.get("turnover", 0),
                "cost_adjusted": result.get("cost_adjusted", False),
                "cost_rate": result.get("cost_rate", 0),
                "total_cost_drag": result.get("total_cost_drag", 0),
            },
            "anti_overfit": anti_overfit_result,
            "params": {
                "expression": expression,
                "universe": req.universe,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "n_groups": req.n_groups,
                "holding_period": req.holding_period,
                "benchmark": req.benchmark,
                "stock_count": len(stock_codes),
            },
            "llm": {
                "prompt": req.prompt,
                "generated_expression": expression,
            },
        }
        logger.info(f"[{task_id}] completed")
        _cleanup_reports(user_id)

    except Exception as e:
        logger.error(f"[{task_id}] failed: {traceback.format_exc()}")
        task["status"] = "failed"
        task["error"] = "回测过程中发生内部错误，请稍后重试"
    finally:
        # Persist to DB when task finishes
        try:
            _persist_task_to_db(task_id, user_id, task, report_filename)
        except Exception as e:
            logger.error(f"[{task_id}] DB persist error: {e}")


# ---- Routes ----

@app.get("/api/v1/health")
def health():
    """健康检查。"""
    return {
        "status": "ok",
        "active_tasks": _active_task_count(),
        "total_tasks": len(_tasks),
    }


@app.post("/api/v1/auto_backtest", status_code=202)
async def auto_backtest(
    req: AutoBacktestRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """提交回测任务，立即返回 task_id，后台异步执行。"""
    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    if _active_task_count() >= MAX_ACTIVE_TASKS:
        raise HTTPException(status_code=503, detail="当前回测任务已满，请稍后再试")

    _cleanup_tasks()

    task_id = uuid.uuid4().hex[:12]
    user_id = str(user.id)
    session_id = req.session_id
    with _tasks_lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "session_id": session_id,
            "status": "pending",
            "params": req.model_dump(exclude={"session_id"}),
            "created_at": time.time(),
        }
    logger.info(f"task {task_id} created for user {user.email}")

    thread = threading.Thread(
        target=_run_backtest_task, args=(task_id, req, user_id), daemon=True
    )
    thread.start()

    return {"task_id": task_id, "status": "pending"}


@app.get("/api/v1/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session_id: str | None = Query(None, description="按会话 ID 过滤"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """分页查询当前用户的任务列表。"""
    user_id = str(user.id)
    offset = (page - 1) * page_size

    # In-memory active tasks for this user
    memory_tasks = []
    with _tasks_lock:
        for t in _tasks.values():
            if t.get("user_id") == user_id:
                if session_id is not None and t.get("session_id") != session_id:
                    continue
                safe = {k: v for k, v in t.items() if k not in ("created_at", "user_id")}
                memory_tasks.append(safe)

    # DB persisted tasks
    query = select(TaskModel).where(TaskModel.user_id == user.id)
    if session_id is not None:
        query = query.where(TaskModel.session_id == session_id)
    query = query.order_by(desc(TaskModel.created_at)).offset(offset).limit(page_size)
    result = await db.execute(query)
    db_tasks = result.scalars().all()

    # Merge: memory tasks override DB tasks with same ID
    memory_ids = {t["task_id"] for t in memory_tasks}
    merged = list(memory_tasks)
    for dt in db_tasks:
        if dt.id not in memory_ids:
            merged.append({
                "task_id": dt.id,
                "status": dt.status,
                "session_id": str(dt.session_id) if dt.session_id else None,
                "params": dt.params,
                "expression": dt.expression,
                "result": dt.result,
                "error": dt.error,
            })

    return {"tasks": merged, "page": page, "page_size": page_size}


@app.get("/api/v1/tasks/{task_id}")
async def get_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询任务状态。completed 时包含完整回测结果。"""
    user_id = str(user.id)

    # Check in-memory first
    task = _tasks.get(task_id)
    if task:
        if task.get("user_id") != user_id:
            raise HTTPException(status_code=404, detail="Task not found")
        safe = {k: v for k, v in task.items() if k not in ("created_at", "user_id")}
        return safe

    # Fallback to DB
    result = await db.execute(
        select(TaskModel).where(TaskModel.id == task_id, TaskModel.user_id == user.id)
    )
    db_task = result.scalar_one_or_none()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": db_task.id,
        "status": db_task.status,
        "params": db_task.params,
        "expression": db_task.expression,
        "result": db_task.result,
        "error": db_task.error,
    }


@app.get("/api/v1/tasks/{task_id}/stream")
async def stream_task(task_id: str, request: Request):
    """SSE 实时推送任务状态变化，直到 completed/failed 后关闭连接。"""
    # Authenticate via query param (EventSource can't set headers)
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="无效的 Token")
    user_id = payload.get("sub")

    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Task not found")

    global _active_sse_count
    with _sse_lock:
        if _active_sse_count >= MAX_SSE_CONNECTIONS:
            raise HTTPException(status_code=503, detail="SSE 连接数已满")
        _active_sse_count += 1

    async def event_generator():
        global _active_sse_count
        try:
            last_status = None
            last_candidates_done = -1
            deadline = time.monotonic() + SSE_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                task = _tasks.get(task_id)
                if not task:
                    yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
                    return

                current_status = task.get("status")
                current_candidates_done = task.get("candidates_done", -1)
                if current_status != last_status or current_candidates_done != last_candidates_done:
                    last_status = current_status
                    last_candidates_done = current_candidates_done
                    safe = {k: v for k, v in task.items() if k not in ("created_at", "user_id")}
                    payload = json.dumps(safe, ensure_ascii=False, default=str)
                    yield f"event: update\ndata: {payload}\n\n"

                    if current_status in ("completed", "failed", "iteration_completed"):
                        yield f"event: done\ndata: {json.dumps({'status': current_status})}\n\n"
                        return

                await asyncio.sleep(0.5)

            # Timeout
            yield f"event: error\ndata: {json.dumps({'error': 'Stream timeout'})}\n\n"
        finally:
            with _sse_lock:
                _active_sse_count = max(0, _active_sse_count - 1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---- Iteration endpoints ----

class IterateRequest(BaseModel):
    n_candidates: int = Field(5, ge=1, le=10, description="候选因子数量")
    run_rolling_validation: bool = Field(False, description="是否运行滚动验证")


def _run_iteration_task(task_id: str, parent_task_id: str, user_id: str, n_candidates: int):
    """Execute iteration in background thread."""
    task = _tasks.get(task_id)
    if not task:
        return

    try:
        # 1. Read parent task result
        parent_task = _tasks.get(parent_task_id)
        if not parent_task or parent_task.get("status") != "completed":
            task["status"] = "failed"
            task["error"] = "父任务未完成"
            return

        parent_result = parent_task.get("result", {})
        parent_expression = parent_task.get("expression", "")
        parent_params = parent_result.get("params", {})

        if not parent_expression:
            task["status"] = "failed"
            task["error"] = "父任务缺少表达式"
            return

        # 2. Set status
        task["status"] = "iterating"
        task["expression"] = parent_expression

        # 3. Fetch market data (from cache, fast)
        stock_codes = get_universe(
            parent_params.get("universe", "hs300"),
            date=parent_params.get("start_date", "2023-01-01"),
        )
        fetcher = MarketDataFetcher()
        market_df = fetcher.fetch_stocks(
            stock_codes,
            parent_params.get("start_date", "2023-01-01"),
            parent_params.get("end_date", "2025-12-31"),
        )
        if market_df is None or len(market_df) == 0:
            task["status"] = "failed"
            task["error"] = "无法获取行情数据"
            return

        # 4. Score parent factor
        parent_backtest_summary = parent_result.get("backtest_summary", {})
        parent_report_metrics = parent_result.get("metrics", {})
        parent_scoring = compute_factor_score(parent_backtest_summary, parent_report_metrics)

        # 5. Generate candidates
        parent_metrics = {
            "backtest_summary": parent_backtest_summary,
            "report_metrics": parent_report_metrics,
        }

        def on_progress(done_count, candidate_result):
            task["candidates_done"] = done_count
            # Append successful candidates to list
            if candidate_result.get("status") == "success":
                task["candidates"].append(candidate_result)
                # Persist report to DB
                report_filename = candidate_result.get("report_filename")
                if report_filename:
                    try:
                        _persist_report_to_db(task_id, user_id, report_filename)
                    except Exception as e:
                        logger.error(f"[{task_id}] report persist error: {e}")
            else:
                task["candidates"].append(candidate_result)

        candidates = generate_iteration_candidates(
            parent_expression=parent_expression,
            parent_metrics=parent_metrics,
            parent_score=parent_scoring["score"],
            parent_grade=parent_scoring["grade"],
            params=parent_params,
            market_df=market_df,
            user_id=user_id,
            n_candidates=n_candidates,
            max_concurrent=3,
            on_progress=on_progress,
            task_id=task_id,
        )

        # 6. Complete — store sorted candidates (replace the incrementally-built list)
        task["candidates"] = candidates
        task["candidates_done"] = len(candidates)
        task["status"] = "iteration_completed"
        task["result"] = {
            "parent_task_id": parent_task_id,
            "parent_expression": parent_expression,
            "parent_score": parent_scoring["score"],
            "parent_grade": parent_scoring["grade"],
            "candidates": candidates,
        }
        logger.info(f"[{task_id}] iteration completed: {len(candidates)} candidates")

    except Exception as e:
        logger.error(f"[{task_id}] iteration failed: {traceback.format_exc()}")
        task["status"] = "failed"
        task["error"] = f"迭代过程中发生错误: {str(e)}"
    finally:
        try:
            _persist_task_to_db(task_id, user_id, task)
        except Exception as e:
            logger.error(f"[{task_id}] DB persist error: {e}")


def _persist_report_to_db(task_id: str, user_id: str, report_filename: str):
    """Persist a report record to DB from background thread."""
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

    if _main_loop and _main_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(_do(), _main_loop)
        try:
            future.result(timeout=30)
        except Exception as e:
            logger.error(f"Report persist error: {e}")
    else:
        logger.error(f"main event loop not available for report persist")


@app.post("/api/v1/tasks/{task_id}/iterate", status_code=202)
async def iterate_task(
    task_id: str,
    req: IterateRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """提交迭代优化任务，基于已完成的回测结果生成候选改进因子。"""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    user_id = str(user.id)

    # Validate parent task
    parent_task = _tasks.get(task_id)
    if not parent_task:
        raise HTTPException(status_code=404, detail="Task not found")
    if parent_task.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    if parent_task.get("status") != "completed":
        raise HTTPException(status_code=400, detail="只能对已完成的任务进行迭代优化")

    if _active_task_count() >= MAX_ACTIVE_TASKS:
        raise HTTPException(status_code=503, detail="当前任务已满，请稍后再试")

    _cleanup_tasks()

    iter_task_id = uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[iter_task_id] = {
            "task_id": iter_task_id,
            "user_id": user_id,
            "status": "pending",
            "task_type": "iteration",
            "parent_task_id": task_id,
            "params": {
                **(parent_task.get("result", {}).get("params", {})),
                "parent_task_id": task_id,
                "n_candidates": req.n_candidates,
            },
            "expression": parent_task.get("expression"),
            "candidates": [],
            "candidates_done": 0,
            "candidates_total": req.n_candidates,
            "created_at": time.time(),
        }
    logger.info(f"iteration task {iter_task_id} created for parent {task_id}")

    thread = threading.Thread(
        target=_run_iteration_task,
        args=(iter_task_id, task_id, user_id, req.n_candidates),
        daemon=True,
    )
    thread.start()

    return {"task_id": iter_task_id, "status": "pending"}


class SelectCandidateRequest(BaseModel):
    candidate_index: int = Field(..., ge=0, description="候选因子索引")


@app.post("/api/v1/tasks/{task_id}/select_candidate")
async def select_candidate(
    task_id: str,
    req: SelectCandidateRequest,
    user: User = Depends(get_current_user),
):
    """选择迭代候选因子。"""
    user_id = str(user.id)

    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") != "iteration_completed":
        raise HTTPException(status_code=400, detail="迭代任务尚未完成")

    candidates = task.get("candidates", [])
    if req.candidate_index >= len(candidates):
        raise HTTPException(status_code=400, detail="候选索引超出范围")

    candidate = candidates[req.candidate_index]
    if candidate.get("status") != "success":
        raise HTTPException(status_code=400, detail="该候选因子回测失败，无法选择")

    task["selected_candidate_index"] = req.candidate_index

    return {
        "task_id": task_id,
        "selected_index": req.candidate_index,
        "expression": candidate.get("expression"),
        "score": candidate.get("score"),
        "grade": candidate.get("grade"),
        "report_url": candidate.get("report_url"),
        "report_metrics": candidate.get("report_metrics"),
        "backtest_summary": candidate.get("backtest_summary"),
    }


_REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
_SAFE_FILENAME_RE = re.compile(r"^backtest_report_[\w]+\.html$")


@app.get("/api/v1/reports/{filename}")
async def get_report(
    filename: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载 HTML 报告文件（验证用户归属）。"""
    if not _SAFE_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    user_id = str(user.id)
    user_report_dir = _REPORT_DIR / user_id
    file_path = (user_report_dir / filename).resolve()

    # Security: ensure path stays within user's report directory
    if not file_path.is_relative_to(user_report_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")

    # Check file exists in user-specific directory (primary check)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(str(file_path), media_type="text/html")


# ---- Feedback ----

_FEEDBACK_DIR = Path(__file__).resolve().parent.parent / "feedback"
_FEEDBACK_WEBHOOK_URL = os.environ.get("QUANTGPT_FEEDBACK_WEBHOOK", "")
_FEEDBACK_WEBHOOK_SECRET = os.environ.get("QUANTGPT_FEEDBACK_WEBHOOK_SECRET", "")
MAX_SCREENSHOT_SIZE = 5 * 1024 * 1024  # 5MB base64


class FeedbackRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000, description="问题描述")
    screenshot: str | None = Field(None, description="截图 base64 (data:image/png;base64,...)")
    task_id: str | None = Field(None, description="关联的任务 ID")
    page_url: str | None = Field(None, max_length=500, description="当前页面 URL")
    user_agent: str | None = Field(None, max_length=500, description="浏览器 UA")


def _feishu_sign(secret: str, timestamp: int) -> str:
    """Generate Feishu webhook signature."""
    import hashlib
    import hmac
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def _send_webhook(webhook_url: str, feedback_data: dict) -> bool:
    """Send feedback to webhook (Feishu). Returns True on success."""
    import httpx

    user_email = feedback_data.get("user_email", "unknown")
    description = feedback_data.get("description", "")
    task_id = feedback_data.get("task_id", "")
    page_url = feedback_data.get("page_url", "")
    created_at = feedback_data.get("created_at", "")
    screenshot_url = feedback_data.get("screenshot_url", "")

    text_parts = [
        f"用户反馈 from {user_email}",
        f"时间: {created_at}",
        f"描述: {description}",
    ]
    if task_id:
        text_parts.append(f"任务ID: {task_id}")
    if page_url:
        text_parts.append(f"页面: {page_url}")
    if screenshot_url:
        text_parts.append(f"截图: {screenshot_url}")

    text = "\n".join(text_parts)

    payload: dict = {
        "msg_type": "text",
        "content": {"text": text},
    }

    # Feishu signature verification
    if _FEEDBACK_WEBHOOK_SECRET:
        timestamp = int(time.time())
        sign = _feishu_sign(_FEEDBACK_WEBHOOK_SECRET, timestamp)
        payload["timestamp"] = str(timestamp)
        payload["sign"] = sign

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(webhook_url, json=payload)
            if resp.status_code < 300:
                return True
            logger.warning(f"Webhook returned {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Webhook send failed: {e}")
        return False


def _save_screenshot_to_disk(feedback_id: str, screenshot_b64: str) -> str | None:
    """Decode base64 screenshot and save to feedback/ directory. Returns relative path."""
    try:
        # Strip data URI prefix if present
        if "," in screenshot_b64:
            screenshot_b64 = screenshot_b64.split(",", 1)[1]
        img_bytes = base64.b64decode(screenshot_b64)

        _FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{feedback_id}.png"
        filepath = _FEEDBACK_DIR / filename
        filepath.write_bytes(img_bytes)
        return str(filepath.relative_to(Path(__file__).resolve().parent.parent))
    except Exception as e:
        logger.error(f"Screenshot save failed: {e}")
        return None


@app.post("/api/v1/feedback", status_code=201)
async def submit_feedback(
    req: FeedbackRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交问题反馈。支持截图和关联任务。"""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    # Validate screenshot size
    if req.screenshot and len(req.screenshot) > MAX_SCREENSHOT_SIZE:
        raise HTTPException(status_code=400, detail="截图文件过大（最大5MB）")

    feedback_id = uuid.uuid4().hex[:16]
    now = datetime.now()

    # Save screenshot
    screenshot_path = None
    if req.screenshot:
        screenshot_path = _save_screenshot_to_disk(feedback_id, req.screenshot)

    # Persist to DB
    feedback_record = FeedbackModel(
        user_id=user.id,
        description=req.description,
        screenshot_path=screenshot_path,
        task_id=req.task_id,
        user_agent=req.user_agent,
        page_url=req.page_url,
        webhook_sent=False,
    )
    db.add(feedback_record)

    # Try webhook
    webhook_sent = False
    if _FEEDBACK_WEBHOOK_URL:
        # Build screenshot URL for webhook message
        screenshot_url = ""
        if screenshot_path:
            host = request.headers.get("host", "localhost:8002")
            scheme = request.headers.get("x-forwarded-proto", "http")
            screenshot_url = f"{scheme}://{host}/api/v1/feedback-screenshots/{feedback_id}"

        feedback_data = {
            "user_email": user.email,
            "description": req.description,
            "task_id": req.task_id,
            "page_url": req.page_url,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "screenshot_url": screenshot_url,
        }
        webhook_sent = _send_webhook(_FEEDBACK_WEBHOOK_URL, feedback_data)
        feedback_record.webhook_sent = webhook_sent

    # Also save as local JSON (always, as backup)
    _FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    local_record = {
        "id": feedback_id,
        "user_email": user.email,
        "description": req.description,
        "task_id": req.task_id,
        "page_url": req.page_url,
        "user_agent": req.user_agent,
        "screenshot_path": screenshot_path,
        "webhook_sent": webhook_sent,
        "created_at": now.isoformat(),
    }
    json_path = _FEEDBACK_DIR / f"{feedback_id}.json"
    json_path.write_text(json.dumps(local_record, ensure_ascii=False, indent=2))

    await db.commit()

    logger.info(f"Feedback {feedback_id} from {user.email} (webhook={'OK' if webhook_sent else 'skip/fail'})")

    return {
        "id": feedback_id,
        "status": "received",
        "webhook_sent": webhook_sent,
    }


_SAFE_FEEDBACK_ID_RE = re.compile(r"^[a-f0-9]{16}$")


@app.get("/api/v1/feedback-screenshots/{feedback_id}")
async def get_feedback_screenshot(feedback_id: str):
    """获取反馈截图（管理员查看，无需认证，但 ID 本身不可猜测）。"""
    # Strip .png suffix if present
    feedback_id = feedback_id.removesuffix(".png")
    if not _SAFE_FEEDBACK_ID_RE.match(feedback_id):
        raise HTTPException(status_code=400, detail="Invalid feedback ID")
    filepath = (_FEEDBACK_DIR / f"{feedback_id}.png").resolve()
    if not filepath.is_relative_to(_FEEDBACK_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(str(filepath), media_type="image/png")


# ---- SPA static files (production: serve frontend/dist) ----

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _mount_spa():
    """Mount frontend static files + SPA fallback if dist exists."""
    if not _FRONTEND_DIST.is_dir():
        return

    assets_dir = _FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    _index_html = _FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        # Only serve files within dist, no traversal
        if full_path and not full_path.startswith("."):
            static_file = (_FRONTEND_DIST / full_path).resolve()
            if static_file.is_file() and static_file.is_relative_to(_FRONTEND_DIST.resolve()):
                return FileResponse(str(static_file))
        if _index_html.is_file():
            return HTMLResponse(_index_html.read_text())
        raise HTTPException(status_code=404, detail="Frontend not built")


_mount_spa()
