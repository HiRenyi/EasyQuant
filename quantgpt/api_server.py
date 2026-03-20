"""REST API server for QuantGPT.

Endpoints:
    POST /api/v1/auto_backtest           — 提交回测任务（异步，立即返回 task_id）
    GET  /api/v1/tasks/{task_id}         — 查询任务状态和结果
    GET  /api/v1/tasks/{task_id}/stream  — SSE 实时推送任务状态
    GET  /api/v1/reports/{filename}      — 下载 HTML 报告
    GET  /api/v1/health                  — 健康检查

启动: DEEPSEEK_API_KEY=sk-xxx python -m quantgpt --transport http --port 8002
"""

import asyncio
import json
import logging
import os
import re
import time
import traceback
import uuid
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .expression_parser import parse_expression
from .expression_parser import __doc__ as _expr_module_doc
from .market_data import MarketDataFetcher, get_universe, fetch_benchmark_returns
from .backtest import run_factor_backtest
from .report import generate_report

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
MAX_DATE_RANGE_YEARS = 5
VALID_UNIVERSES = {"small_scale", "hs300", "csi500"}
VALID_BENCHMARKS = {"hs300", "zz500", "sz50"}

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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


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
    """Count tasks that are still running (not completed/failed)."""
    return sum(
        1 for t in _tasks.values()
        if t.get("status") not in ("completed", "failed")
    )


def _cleanup_tasks():
    """Remove expired tasks and cap total count."""
    now = time.time()
    with _tasks_lock:
        # Remove expired
        expired = [
            tid for tid, t in _tasks.items()
            if now - t.get("created_at", now) > TASK_TTL_SECONDS
            and t.get("status") in ("completed", "failed")
        ]
        for tid in expired:
            _tasks.pop(tid, None)
        # If still over limit, remove oldest completed
        if len(_tasks) > MAX_TOTAL_TASKS:
            completed = sorted(
                [(tid, t) for tid, t in _tasks.items() if t.get("status") in ("completed", "failed")],
                key=lambda x: x[1].get("created_at", 0),
            )
            for tid, _ in completed[:len(_tasks) - MAX_TOTAL_TASKS]:
                _tasks.pop(tid, None)


def _cleanup_reports():
    """Remove oldest report files if over limit."""
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
    start_date: str = Field("2022-01-01", description="起始日期 YYYY-MM-DD")
    end_date: str = Field("2024-12-31", description="结束日期 YYYY-MM-DD")
    n_groups: int = Field(5, description="分组数量", ge=2, le=20)
    holding_period: int = Field(5, description="持仓周期(交易日)", ge=1, le=60)
    benchmark: str = Field("hs300", description="基准指数: hs300 / zz500 / sz50")

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

_OPERATORS_DOC = """
一元函数: rank, zscore, sign, log, abs, scale, tanh, sigmoid, exp, sqrt
时序函数: ts_mean, ts_std, ts_max, ts_min, ts_sum, ts_shift, ts_delta, ts_rank, ts_argmax, ts_argmin, decay_linear, product
双列时序: ts_corr(col1, col2, N), ts_cov(col1, col2, N)
二元函数: power, max, min
条件函数: clip(expr, lo, hi), where(cond, t, f)
算术运算: +, -, *, /, ^
可用列名: open, high, low, close, volume, amount, pct_change
特殊变量: vwap, returns, adv{N}
别名: delta=ts_delta, delay=ts_shift, correlation=ts_corr, covariance=ts_cov
"""

_SYSTEM_PROMPT = """你是一个量化因子表达式生成器。用户会用自然语言描述想要的因子，你需要生成一个合法的因子表达式。

可用算子:
{operators}

规则:
1. 只输出一个因子表达式，不要任何解释、markdown 或代码块
2. 表达式必须可直接被解析器执行
3. 可用列名: open, high, low, close, volume, amount, pct_change
4. 特殊变量: vwap, returns, adv{{N}}
5. 如果用户描述模糊，选择最常见的实现方式

示例:
- "动量因子" → rank(close/ts_mean(close, 20))
- "成交量异动" → rank(volume/ts_mean(volume, 10))
- "波动率因子" → ts_std(close/ts_shift(close, 1) - 1, 20)
- "反转因子" → rank(-1 * ts_delta(close, 5) / ts_shift(close, 5))
- "量价相关性" → rank(ts_corr(close, volume, 10))
"""


def _call_deepseek(prompt: str) -> str:
    """Call DeepSeek API to generate factor expression."""
    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    client = OpenAI(api_key=api_key, base_url=base_url)
    operators_doc = _expr_module_doc or _OPERATORS_DOC
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
    expression = resp.choices[0].message.content.strip()
    if expression.startswith("```"):
        expression = expression.split("\n", 1)[-1]
    if expression.endswith("```"):
        expression = expression.rsplit("```", 1)[0]
    return expression.strip()


# ---- Background worker ----

def _run_backtest_task(task_id: str, req: AutoBacktestRequest):
    """Execute backtest in background thread, update task store."""
    task = _tasks.get(task_id)
    if not task:
        return
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
        logger.info(f"[{task_id}] expression generated")

        # 2. Validate expression
        task["status"] = "validating"
        try:
            func = parse_expression(expression)
            dummy = pd.DataFrame({
                "open": [1.0, 2.0, 3.0], "high": [1.1, 2.1, 3.1],
                "low": [0.9, 1.9, 2.9], "close": [1.0, 2.0, 3.0],
                "volume": [100, 200, 300], "amount": [100, 400, 900],
                "pct_change": [0, 100, 50],
            })
            func(dummy)
        except Exception:
            task["status"] = "failed"
            task["error"] = "生成的因子表达式无效，请换一种描述方式重试"
            return

        # 3. Fetch data
        task["status"] = "fetching_data"
        stock_codes = get_universe(req.universe)
        fetcher = MarketDataFetcher()
        market_df = fetcher.fetch_stocks(stock_codes, req.start_date, req.end_date)
        if market_df is None or len(market_df) == 0:
            task["status"] = "failed"
            task["error"] = "未获取到行情数据，请检查日期范围"
            return

        # 4. Run backtest
        task["status"] = "backtesting"
        result = run_factor_backtest(market_df, expression, req.n_groups, req.holding_period)

        # 5. Generate report
        task["status"] = "generating_report"
        bm_returns = None
        try:
            bm_returns = fetch_benchmark_returns(req.benchmark, req.start_date, req.end_date)
        except Exception:
            logger.warning(f"[{task_id}] benchmark fetch failed")

        report_result = generate_report(
            result["ls_returns"],
            benchmark_returns=bm_returns,
            title=f"Factor: {expression}",
        )
        report_filename = Path(report_result["report_path"]).name

        # Done
        task["status"] = "completed"
        task["result"] = {
            "report_url": f"/api/v1/reports/{report_filename}",
            "metrics": report_result["metrics"],
            "backtest_summary": {
                "long_short_sharpe": result["long_short_sharpe"],
                "monotonicity_score": result["monotonicity_score"],
                "spread": result["spread"],
                "group_returns": result["group_returns"],
            },
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
        _cleanup_reports()

    except Exception as e:
        logger.error(f"[{task_id}] failed: {traceback.format_exc()}")
        task["status"] = "failed"
        task["error"] = "回测过程中发生内部错误，请稍后重试"


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
def auto_backtest(req: AutoBacktestRequest, request: Request):
    """提交回测任务，立即返回 task_id，后台异步执行。"""
    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    if _active_task_count() >= MAX_ACTIVE_TASKS:
        raise HTTPException(status_code=503, detail="当前回测任务已满，请稍后再试")

    _cleanup_tasks()

    task_id = uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "params": req.model_dump(),
            "created_at": time.time(),
        }
    logger.info(f"task {task_id} created")

    thread = threading.Thread(target=_run_backtest_task, args=(task_id, req), daemon=True)
    thread.start()

    return {"task_id": task_id, "status": "pending"}


@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id: str):
    """查询任务状态。completed 时包含完整回测结果。"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    # Don't expose internal fields
    safe = {k: v for k, v in task.items() if k != "created_at"}
    return safe


@app.get("/api/v1/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """SSE 实时推送任务状态变化，直到 completed/failed 后关闭连接。"""
    if task_id not in _tasks:
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
            deadline = time.monotonic() + SSE_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                task = _tasks.get(task_id)
                if not task:
                    yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
                    return

                current_status = task.get("status")
                if current_status != last_status:
                    last_status = current_status
                    safe = {k: v for k, v in task.items() if k != "created_at"}
                    payload = json.dumps(safe, ensure_ascii=False, default=str)
                    yield f"event: update\ndata: {payload}\n\n"

                    if current_status in ("completed", "failed"):
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


_REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
_SAFE_FILENAME_RE = re.compile(r"^backtest_report_[\w]+\.html$")


@app.get("/api/v1/reports/{filename}")
def get_report(filename: str):
    """下载 HTML 报告文件。"""
    if not _SAFE_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = (_REPORT_DIR / filename).resolve()
    if not file_path.is_relative_to(_REPORT_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(str(file_path), media_type="text/html")


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
