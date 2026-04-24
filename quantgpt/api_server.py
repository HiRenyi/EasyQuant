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

启动: DEEPSEEK_API_KEY=sk-xxx python -m quantgpt --transport http --port 8003
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
import hashlib
import hmac as _hmac_mod
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
from .models import User, Task as TaskModel, Report as ReportModel, Feedback as FeedbackModel, Session as SessionModel, PaperStrategy
from .auth import get_current_user, get_optional_user, decode_token, GUEST_USER_ID
from .routes.auth import router as auth_router
from .routes.sessions import router as sessions_router
from .routes.admin import router as admin_router
from .routes.factor_library import router as factor_library_router
from .routes.templates import router as templates_router
from .routes.composite import router as composite_router
from .routes.comparison import router as comparison_router
from .routes.paper import router as paper_router
from .routes.daily_summary import router as daily_summary_router
from .routes.strategy_backtest import router as strategy_backtest_router

logger = logging.getLogger(__name__)

def _sanitize_task_response(task_dict: dict) -> dict:
    """Pass through task dict (obfuscation layer removed)."""
    return task_dict if isinstance(task_dict, dict) else task_dict


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
from .schemas import VALID_UNIVERSES, VALID_BENCHMARKS

# ---- Lifespan ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    await init_db()
    logger.info("Database initialized")

    # Start paper trading scheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from zoneinfo import ZoneInfo
    from .scheduler_registry import register_scheduler, register_job, record_job_run
    CST = ZoneInfo("Asia/Shanghai")
    scheduler = AsyncIOScheduler()

    async def _paper_settlement_job():
        from .paper_engine import run_daily_settlement
        from .db import _get_session_factory
        async with _get_session_factory()() as db:
            try:
                await run_daily_settlement(db)
                record_job_run("paper_settlement", "success")
            except Exception as e:
                logger.error(f"Paper settlement job failed: {e}")
                record_job_run("paper_settlement", "failed", str(e))

    # Run at 16:30 Beijing time on weekdays
    scheduler.add_job(_paper_settlement_job, CronTrigger(hour=16, minute=30, day_of_week="mon-fri", timezone=CST), id="paper_settlement")
    register_job("paper_settlement", "模拟盘日结算", "每个交易日收盘后结算模拟持仓盈亏", "周一至周五 16:30 CST")

    # Market data refresh: every weekday 15:10 CST (after market close at 15:00)
    async def _market_data_refresh_job():
        import asyncio
        from .market_data import refresh_all_cached_stocks
        try:
            await asyncio.to_thread(refresh_all_cached_stocks)
            record_job_run("market_data_refresh", "success")
        except Exception as e:
            logger.error(f"Market data refresh failed: {e}")
            record_job_run("market_data_refresh", "failed", str(e))

    scheduler.add_job(_market_data_refresh_job, CronTrigger(hour=15, minute=10, day_of_week="mon-fri", timezone=CST), id="market_data_refresh")
    register_job("market_data_refresh", "行情数据增量更新", "收盘后从 akshare/baostock 增量更新缓存（禁用 rqdatac）", "周一至周五 15:10 CST")

    # Factor deep research report: every Monday 9:03 CST = 01:03 UTC
    async def _weekly_report_job():
        from .weekly_report import get_latest_report_content, send_weekly_report
        from .db import _get_session_factory
        md = get_latest_report_content()
        if not md:
            logger.warning("Factor research job: no report file found")
            record_job_run("weekly_report", "skipped", "no report file found")
            return
        async with _get_session_factory()() as db:
            try:
                stats = await send_weekly_report(db, md)
                logger.info(f"Factor research job completed: {stats}")
                record_job_run("weekly_report", "success")
            except Exception as e:
                logger.error(f"Factor research job failed: {e}")
                record_job_run("weekly_report", "failed", str(e))

    scheduler.add_job(_weekly_report_job, CronTrigger(hour=9, minute=3, day_of_week="mon", timezone=CST), id="weekly_report")
    register_job("weekly_report", "因子研究周报", "每周一发送因子深度研究报告邮件给订阅用户", "每周一 09:03 CST")

    # Daily market summary: 15:30 CST = 07:30 UTC on weekdays
    async def _daily_summary_job():
        from .daily_summary import generate_daily_summary
        from .db import _get_session_factory
        async with _get_session_factory()() as db:
            try:
                await generate_daily_summary(db, market="a_share")
                logger.info("Daily summary job completed")
                record_job_run("daily_summary", "success")
            except Exception as e:
                logger.error(f"Daily summary job failed: {e}")
                record_job_run("daily_summary", "failed", str(e))

    scheduler.add_job(_daily_summary_job, CronTrigger(hour=15, minute=30, day_of_week="mon-fri", timezone=CST), id="daily_summary")
    register_job("daily_summary", "每日大盘报告", "每个交易日收盘后生成因子信号驱动的市场解读报告", "周一至周五 15:30 CST")

    register_scheduler(scheduler)
    scheduler.start()
    logger.info("Paper trading scheduler started (weekdays 16:30 CST)")
    logger.info("Factor research report scheduler started (Monday 09:03 CST)")

    # Start MCP session manager
    from .mcp_server import mcp as _mcp_server
    _mcp_server.streamable_http_app()  # lazy-init session manager
    async with _mcp_server.session_manager.run():
        logger.info("MCP streamable-http session manager started")

        # Start JoinQuant browser (if credentials configured)
        jq_username = os.environ.get("JQ_USERNAME", "")
        jq_password = os.environ.get("JQ_PASSWORD", "")
        if jq_username and jq_password:
            try:
                from .jq_automation import get_jq_service
                jq = get_jq_service()
                ok = await jq.startup()
                if ok:
                    logger.info("JoinQuant browser started and logged in")
                else:
                    logger.warning("JoinQuant browser login failed — strategy backtest may not work")
            except Exception as e:
                logger.error(f"JoinQuant browser startup error: {e}")
        else:
            logger.info("JQ_USERNAME/JQ_PASSWORD not set — skipping JoinQuant browser")

        yield

    # Shutdown JQ browser
    try:
        from .jq_automation import get_jq_service
        jq = get_jq_service()
        await jq.shutdown()
    except Exception:
        pass

    scheduler.shutdown(wait=False)
    await close_db()
    _main_loop = None
    logger.info("Database connection closed")

# ---- App ----

_cors_origins = os.environ.get("QUANTGPT_CORS_ORIGINS", "*")
_cors_list = [o.strip() for o in _cors_origins.split(",") if o.strip()]

app = FastAPI(
    title="QuantGPT API",
    version="2.5.0",
    description="QuantGPT — AI 驱动的量化策略回测平台",
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
app.include_router(factor_library_router)
app.include_router(templates_router)
app.include_router(composite_router)
app.include_router(comparison_router)
app.include_router(paper_router)
app.include_router(daily_summary_router)
app.include_router(strategy_backtest_router)


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
    """Count tasks that are still running (not completed/failed/cancelled/iteration_completed)."""
    return sum(
        1 for t in _tasks.values()
        if t.get("status") not in ("completed", "failed", "cancelled", "iteration_completed")
    )


class _CancelledException(Exception):
    """Raised when a task is cancelled by the user."""
    pass


def _check_cancelled(task_id: str):
    """Check if task has been cancelled; raise if so."""
    task = _tasks.get(task_id)
    if task and task.get("cancelled"):
        raise _CancelledException()


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

from .schemas import validate_date_format as _validate_date_fn, validate_universe_value as _validate_univ_fn, validate_benchmark_value as _validate_bench_fn


class AutoBacktestRequest(BaseModel):
    prompt: str = Field(..., description="自然语言描述", examples=["帮我测试一个20日动量因子"])
    universe: str = Field("hs300", description="股票池")
    start_date: str = Field("2023-01-01", description="起始日期 YYYY-MM-DD")
    end_date: str = Field("2025-12-31", description="结束日期 YYYY-MM-DD")
    n_groups: int = Field(5, description="分组数量", ge=2, le=20)
    holding_period: int = Field(5, description="持仓周期(交易日)", ge=1, le=60)
    benchmark: str = Field("hs300", description="基准指数")
    session_id: str | None = Field(None, description="关联会话 ID")
    neutralize_industry: bool = Field(True, description="行业中性化")
    neutralize_cap: bool = Field(True, description="市值中性化")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("prompt 不能为空")
        if len(v) > MAX_PROMPT_LENGTH:
            raise ValueError(f"prompt 长度不能超过 {MAX_PROMPT_LENGTH} 字符")
        return v

    _validate_universe = field_validator("universe")(_validate_univ_fn)
    _validate_benchmark = field_validator("benchmark")(_validate_bench_fn)
    _validate_dates = field_validator("start_date", "end_date")(_validate_date_fn)


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
Technical indicators: ema(col,N), sma(col,N), wma(col,N), rsi(col,N), macd(col,N),
  boll_upper(col,N), boll_lower(col,N), boll_mid(col,N), obv(col,N), atr(N)
Dual-column: ts_corr(col1,col2,N), ts_cov(col1,col2,N)
Nonlinear: power(base,exp), sign_power(base,exp), tanh(expr), sigmoid(expr), exp(expr), sqrt(expr)
Conditional: max(a,b), min(a,b), where(cond,true_val,false_val), clip(expr,lower,upper)
Arithmetic: +, -, *, /, ^ (power)
Comparison: >, <, >=, <=, ==, !=
Logical: and, or (combine conditions in where())
Columns: open, high, low, close, volume, amount, pct_change
Special vars: vwap, adv{N} (e.g. adv20), returns, cap
Fundamental (精确变量名，不可用其他别名):
  盈利: roe, np_margin, gp_margin, net_profit, eps_ttm, revenue
  股本: total_share, float_share
  成长: yoy_ni, yoy_equity, yoy_asset, yoy_pni
  偿债: current_ratio, debt_ratio, equity_multiplier
  运营: asset_turnover, inv_turnover, dupont_roe, dupont_asset_turn
  现金流: cfo_to_np
  估值(衍生): pe, pb, ps, roa, bps, nav, dividend_yield
  ⚠️ 禁止使用的变量(会导致报错): pe_ratio, pe_ttm, pb_ratio, ps_ratio, roe_avg
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
价值因子: rank(-1 * pe)
质量因子: rank(roe * asset_turnover)
成长因子: rank(yoy_ni)
基本面+动量: rank(roe) * rank(ts_delta(close, 20) / ts_shift(close, 20))
高股息: rank(dividend_yield) * rank(-1 * ts_std(returns, 20))
技术指标-RSI: rank(-1 * rsi(close, 14))
技术指标-MACD: rank(macd(close, 26))
技术指标-布林带: rank((close - boll_lower(close, 20)) / (boll_upper(close, 20) - boll_lower(close, 20) + 1e-10))
技术指标-EMA动量: rank(ema(close, 5) / ema(close, 20) - 1)
技术指标-ATR波动: rank(-1 * atr(14) / close)
================================================================================
"""

_OPERATORS_DOC = _FACTOR_OPERATORS  # backward compat alias

_SYSTEM_PROMPT = """你是一个量化因子表达式生成器。用户会用自然语言描述想要的因子，你需要生成一个合法的因子表达式。

{operators}

================================================================================
⚠️ 关键注意事项
================================================================================
- 🚨 只能使用上面 SUPPORTED OPERATORS 中列出的函数，禁止使用 bbands, adx 等未列出的函数
- 🚨 技术指标已支持：ema(col,N) EMA, sma(col,N) 简单均线, wma(col,N) 加权均线, rsi(col,N) RSI(0~100), macd(col,N) MACD柱状图, atr(N) 真实波幅(用high/low/close), boll_upper/boll_lower/boll_mid(col,N) 布林带, obv(col,N) OBV滚动和
- 🚨 变量名必须严格匹配：pe_ratio→pe, pe_ttm→pe, pb_ratio→pb, eps→eps_ttm, div_yield→dividend_yield
- 🚨 如果用户要求的指标不在支持列表中，用最接近的已支持变量替代，并在表达式中注释说明
- ts_rank(col, N) 返回百分位排名，范围 0~1（不是 0~100），与之比较时用 0.3 而非 30
- where() 条件会使因子值变成离散值（如 -1, 0, 1），可能导致分组失败，尽量避免使用
- 优先使用连续值因子表达式（如 rank(), zscore(), ts_mean() 等），分组效果更好
- returns 是日收益率（等同于 pct_change，如 0.02 代表 2%），close 是收盘价
- day/weekday/month 是日期特殊变量，仅在用户明确要求日历效应时使用
- 基本面变量(roe, pe, yoy_ni 等)是季度财报按发布日对齐到日频的，变化较慢
- 估值因子通常取负值排序(低估值更好)：rank(-1 * pe)
- 推荐将基本面与价量信号组合：rank(roe) * rank(ts_delta(close, 20)/close)

================================================================================
🎯 因子质量指南（非常重要）
================================================================================
简单单因子（如 rank(ts_delta(close, 20))）通常 Sharpe < 0.3，效果很差。
请优先生成**多信号复合因子**，结合不同维度的信息：

高质量因子设计原则：
1. 多维度组合：结合价格动量 + 成交量 + 波动率等至少2个维度
2. 非线性变换：使用 sign_power, tanh, sigmoid 捕捉非线性关系
3. 多周期信号：组合短期(5日)和中期(20日)信号，捕获不同频率
4. 截面标准化：最外层用 rank() 或 zscore() 保证因子截面可比
5. 适度复杂度：3-6层嵌套为宜，避免过度简单也避免过度复杂

避免生成以下低效因子：
- 仅包含单一算子的简单因子：rank(close), rank(ts_delta(close, 20))
- 仅调整窗口参数的同质因子：ts_mean(close, 5) - ts_mean(close, 20)
- 纯离散型因子（大量使用 where 生成 -1/0/1 值）

================================================================================
📈 WorldQuant Fitness 优化策略
================================================================================
Fitness = Sharpe × √(|Returns| / max(Turnover, 0.125))
三个杠杆：高 Sharpe、高绝对收益、低换手率。

提升 Fitness 的关键技巧（按优先级排列）：
1. ts_decay_linear() 包裹最终信号：ts_decay_linear(rank(signal), 5~10)，平滑信号降低换手率
2. rank() 是最关键算子：将原始信号转为百分位，消除量纲偏差，提升单调性
3. ts_zscore(col, N) 取代原始值：ts_zscore(pe, 63) 捕捉变化而非水平
4. 双重排名（时序+截面）：rank(ts_rank(col, 40)) 双重过滤提高稳定性
5. 相关性过滤：-ts_av_diff(x, 50) * ts_corr(x, y, 50) 仅在结构性有效时入场
6. trade_when 波动率门控：trade_when(vol<threshold, signal, 0) 大幅降低换手率

高 Fitness 模板（可直接使用或改编）：
- ts_decay_linear(rank((vwap-close)/close), 5)                 — Fitness ~2.86
- rank(ts_rank(close/ts_shift(close,5)-1, 40))                 — Fitness ~1.42-1.58
- -ts_av_diff(close, 50) * ts_corr(close, volume, 50)          — Fitness ~1.70
- -rank(ts_zscore(pe, 63))                                     — Fitness ~1.26-1.70
- trade_when(ts_std(returns,20)<threshold, rank(signal), 0)    — 最强降换手算子

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


_INTERPRET_SYSTEM = """你是一位专业的量化研究员，擅长用通俗语言解读因子表达式的经济含义并撰写研究报告。

你的任务是解读一个因子表达式，输出 JSON，格式如下：
{
  "logic": "因子的核心逻辑（1-2句，说明该因子捕捉了什么市场现象）",
  "source": "收益来源（1-2句，说明为什么这个因子能产生超额收益，背后的行为金融或基本面逻辑）",
  "guidance": "交易指导（2-4句，从经济含义角度指导用户如何利用该因子思路交易，禁止推荐具体标的，聚焦行为规律和风险提示）",
  "risk": "主要风险（1句，说明该因子在什么市场环境下容易失效）",
  "conclusion": "核心结论（2-3句，总结因子整体表现和是否推荐使用）",
  "suggestions": ["改进建议1", "改进建议2"]
}

注意：评级(rating)由系统算法自动生成，你不需要输出评级。

交易指导要求：
- 禁止推荐任何具体标的
- 从行为金融角度出发，指出市场参与者的非理性行为
- 结合回测指标（如换手率、IC、单调性）给出实操建议
- 语言简洁，面向普通投资者

只输出 JSON，不要任何额外文字。"""

def _call_interpret_factor(
    expression: str,
    prompt: str,
    metrics: dict,
    backtest_summary: dict,
) -> dict:
    """Call LLM to interpret factor economic meaning."""
    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {}
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    client = OpenAI(api_key=api_key, base_url=base_url)

    sharpe = metrics.get("sharpe", 0)
    cagr = metrics.get("cagr", 0)
    max_dd = metrics.get("max_drawdown", 0)
    ic = backtest_summary.get("ic_mean", 0)
    rank_ic = backtest_summary.get("rank_ic_mean", 0)
    mono = backtest_summary.get("monotonicity_score", 0)
    turnover = backtest_summary.get("turnover", 0)

    user_msg = (
        f"用户需求：{prompt}\n"
        f"因子表达式：{expression}\n\n"
        f"回测指标（供参考）：\n"
        f"- 年化收益：{cagr*100:.1f}%，Sharpe：{sharpe:.2f}，最大回撤：{max_dd*100:.1f}%\n"
        f"- IC均值：{ic:.4f}，Rank IC：{rank_ic:.4f}，单调性：{mono:.2f}，换手率：{turnover*100:.1f}%\n"
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _INTERPRET_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=600,
            timeout=30,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code block if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Factor interpretation failed: {e}")
        return {}


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


# ---- Expression detection ----

# Keywords that indicate factor expression syntax (not natural language)
_EXPR_KEYWORDS = re.compile(
    r'(?:rank|zscore|ts_mean|ts_std|ts_delta|ts_shift|ts_rank|ts_corr|ts_cov|'
    r'ts_max|ts_min|ts_sum|ts_argmax|ts_argmin|decay_linear|product|sign_power|'
    r'where|clip|log|abs|sign|scale|tanh|sigmoid|exp|sqrt|power)\s*\('
)


def _looks_like_expression(text: str) -> bool:
    """Heuristic: does the text look like a factor expression rather than natural language?"""
    # Contains factor function calls
    if _EXPR_KEYWORDS.search(text):
        return True
    # Bare column arithmetic like "close / open" or "-1 * close"
    from .fundamental_data import ALL_FUNDAMENTAL_NAMES as _FN
    cols = {'open', 'high', 'low', 'close', 'volume', 'amount', 'returns', 'vwap'} | _FN
    tokens = re.findall(r'[a-zA-Z_]\w*', text)
    if tokens and all(t in cols for t in tokens):
        return True
    return False


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

        # 1. Check if user input is already a valid factor expression
        task["status"] = "generating_expression"
        expression = None
        user_text = req.prompt.strip()
        if _looks_like_expression(user_text):
            try:
                from .fundamental_data import ALL_FUNDAMENTAL_NAMES as _FUND_NAMES
                _test_dummy = pd.DataFrame({
                    "open": [1.0, 2.0, 3.0], "high": [1.1, 2.1, 3.1],
                    "low": [0.9, 1.9, 2.9], "close": [1.0, 2.0, 3.0],
                    "volume": [100, 200, 300], "amount": [100, 400, 900],
                    "pct_change": [0, 100, 50],
                    "trade_date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                    **{name: [1.0, 1.1, 1.2] for name in _FUND_NAMES},
                })
                parse_expression(user_text)(_test_dummy)
                expression = user_text
                logger.info(f"[{task_id}] user input is a valid expression, using directly: {expression}")
            except Exception:
                pass  # Not a valid expression, fall through to LLM

        if expression is None:
            expression = _call_deepseek(req.prompt)
        task["expression"] = expression
        logger.info(f"[{task_id}] expression: {expression}")

        # 2. Validate expression (with fix-retry)
        task["status"] = "validating"
        from .fundamental_data import ALL_FUNDAMENTAL_NAMES as _FUND_NAMES2
        dummy = pd.DataFrame({
            "open": [1.0, 2.0, 3.0], "high": [1.1, 2.1, 3.1],
            "low": [0.9, 1.9, 2.9], "close": [1.0, 2.0, 3.0],
            "volume": [100, 200, 300], "amount": [100, 400, 900],
            "pct_change": [0, 100, 50],
            "trade_date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            **{name: [1.0, 1.1, 1.2] for name in _FUND_NAMES2},
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
        _check_cancelled(task_id)
        task["status"] = "fetching_data"
        stock_codes = get_universe(req.universe, date=req.start_date)
        fetcher = MarketDataFetcher()
        market_df = fetcher.fetch_stocks(stock_codes, req.start_date, req.end_date)
        if market_df is None or len(market_df) == 0:
            task["status"] = "failed"
            task["error"] = "未获取到行情数据，请检查日期范围"
            return

        # 3a. Fetch fundamental data if expression uses fundamental vars
        from .fundamental_data import detect_fundamental_vars, FundamentalDataFetcher, enrich_with_fundamentals_rq
        fund_vars = detect_fundamental_vars(expression)
        if fund_vars:
            _check_cancelled(task_id)
            task["status"] = "fetching_fundamentals"
            logger.info(f"[{task_id}] fetching fundamentals for vars: {fund_vars}")
            rq_result = enrich_with_fundamentals_rq(market_df, fund_vars, stock_codes, req.start_date, req.end_date)
            if rq_result is not None:
                market_df = rq_result
                logger.info(f"[{task_id}] fundamental data merged via rqdatac")
            else:
                fund_fetcher = FundamentalDataFetcher()
                non_div_vars = fund_vars - {"dividend_yield"}
                if non_div_vars:
                    qdf = fund_fetcher.fetch_fundamentals(stock_codes, req.start_date, req.end_date, non_div_vars)
                    if qdf is not None and len(qdf) > 0:
                        market_df = fund_fetcher.align_to_daily(qdf, market_df, non_div_vars)
                        logger.info(f"[{task_id}] fundamental data merged")
                if "dividend_yield" in fund_vars:
                    div_df = fund_fetcher.fetch_dividend_data(stock_codes, req.start_date, req.end_date)
                    if div_df is not None and len(div_df) > 0:
                        market_df = fund_fetcher.align_dividends_to_daily(div_df, market_df)
                        logger.info(f"[{task_id}] dividend data merged")
                    else:
                        logger.warning(f"[{task_id}] no dividend data fetched")

        # 4. Run backtest
        _check_cancelled(task_id)
        task["status"] = "backtesting"
        result = run_factor_backtest(market_df, expression, req.n_groups, req.holding_period,
                                     neutralize_industry=req.neutralize_industry,
                                     neutralize_cap=req.neutralize_cap,
                                     trading_days_per_year=252)

        # 4a. Anti-overfit analysis
        _check_cancelled(task_id)
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
        _check_cancelled(task_id)
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
            periods_per_year=252,
        )
        report_filename = Path(report_result["report_path"]).name

        # 5b. Factor interpretation (non-blocking, best-effort)
        interpretation = {}
        try:
            interpretation = _call_interpret_factor(
                expression=expression,
                prompt=req.prompt,
                metrics=report_result["metrics"],
                backtest_summary={
                    "ic_mean": result.get("ic_mean", 0),
                    "rank_ic_mean": result.get("rank_ic_mean", 0),
                    "monotonicity_score": result["monotonicity_score"],
                    "turnover": result.get("turnover", 0),
                },
            )
        except Exception as e:
            logger.warning(f"[{task_id}] interpretation failed: {e}")

        # 5c. Deterministic scoring (unified with MCP/iteration)
        ao_score_val = anti_overfit_result.get("score") if anti_overfit_result else None
        scoring = compute_factor_score(
            backtest_summary={
                "long_short_sharpe": result["long_short_sharpe"],
                "monotonicity_score": result["monotonicity_score"],
                "spread": result["spread"],
                "ic_mean": result.get("ic_mean", 0),
                "rank_ic_mean": result.get("rank_ic_mean", 0),
                "ic_ir": result.get("ic_ir", 0),
                "ic_win_rate": result.get("ic_win_rate", 0),
                "wq_fitness": result.get("wq_fitness", 0),
            },
            report_metrics=report_result["metrics"],
            anti_overfit_score=ao_score_val,
        )
        # Inject deterministic grade into interpretation for frontend compatibility
        interpretation["rating"] = scoring["grade"]
        interpretation["rating_reason"] = f"综合评分 {scoring['score']}/100"

        # Done
        task["status"] = "completed"

        # Build NAV series for share card (downsample to ~50 points)
        nav_series = []
        try:
            strat_ret = result["strategy_returns"]
            if hasattr(strat_ret, "index") and len(strat_ret) > 0:
                cum = (1 + strat_ret).cumprod()
                step = max(1, len(cum) // 50)
                sampled = cum.iloc[::step]
                if sampled.index[-1] != cum.index[-1]:
                    sampled = pd.concat([sampled, cum.iloc[[-1]]])
                nav_series = [
                    {"date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d), "value": round(float(v), 4)}
                    for d, v in sampled.items()
                ]
        except Exception:
            pass

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
                "wq_fitness": result.get("wq_fitness", 0),
                "cost_adjusted": result.get("cost_adjusted", False),
                "cost_rate": result.get("cost_rate", 0),
                "total_cost_drag": result.get("total_cost_drag", 0),
            },
            "wq_brain": result.get("wq_brain", {}),
            "anti_overfit": anti_overfit_result,
            "scoring": scoring,
            "interpretation": interpretation,
            "stock_factor_data": result.get("_stock_factor_data"),
            "nav_series": nav_series,
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

    except _CancelledException:
        logger.info(f"[{task_id}] cancelled by user")
        task["status"] = "cancelled"
    except Exception as e:
        logger.error(f"[{task_id}] failed: {traceback.format_exc()}")
        task["status"] = "failed"
        task["error"] = "回测过程中发生内部错误，请稍后重试"
    finally:
        # Persist to DB when task finishes (skip for guest tasks)
        if not task.get("is_guest"):
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


@app.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    user: User | None = Depends(get_optional_user),
):
    """取消正在运行的回测任务。"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # Check ownership
    user_id = str(user.id) if user else GUEST_USER_ID
    if task.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权操作此任务")

    # Only running tasks can be cancelled
    if task["status"] in ("completed", "failed", "cancelled", "iteration_completed"):
        raise HTTPException(status_code=400, detail="任务已结束，无法取消")

    with _tasks_lock:
        task["cancelled"] = True
        task["status"] = "cancelled"

    logger.info(f"[{task_id}] cancel requested by user")
    return {"task_id": task_id, "status": "cancelled"}


@app.post("/api/v1/auto_backtest", status_code=202)
async def auto_backtest(
    req: AutoBacktestRequest,
    request: Request,
    user: User | None = Depends(get_optional_user),
):
    """提交回测任务，立即返回 task_id，后台异步执行。"""
    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    if _active_task_count() >= MAX_ACTIVE_TASKS:
        raise HTTPException(status_code=503, detail="当前回测任务已满，请稍后再试")

    _cleanup_tasks()

    is_guest = user is None
    task_id = uuid.uuid4().hex[:12]
    user_id = str(user.id) if user else GUEST_USER_ID
    session_id = req.session_id

    # Guest restrictions: force small universe, limit params
    if is_guest:
        req.universe = "small_scale"
        session_id = None

    with _tasks_lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "session_id": session_id,
            "status": "pending",
            "cancelled": False,
            "params": req.model_dump(exclude={"session_id"}),
            "created_at": time.time(),
            "is_guest": is_guest,
        }
    logger.info(f"task {task_id} created for {'guest' if is_guest else user.email}")

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
    task_type: str | None = Query(None, description="按任务类型过滤: backtest / strategy_backtest / iteration"),
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
                if task_type is not None and t.get("task_type") != task_type:
                    continue
                safe = {k: v for k, v in t.items() if k not in ("created_at", "user_id")}
                memory_tasks.append(safe)

    # DB persisted tasks
    query = select(TaskModel).where(TaskModel.user_id == user.id)
    if session_id is not None:
        query = query.where(TaskModel.session_id == session_id)
    if task_type is not None:
        query = query.where(TaskModel.task_type == task_type)
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
                "task_type": dt.task_type,
                "session_id": str(dt.session_id) if dt.session_id else None,
                "params": dt.params,
                "expression": dt.expression,
                "result": dt.result,
                "error": dt.error,
            })

    return {"tasks": [_sanitize_task_response(t) for t in merged], "page": page, "page_size": page_size}


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
        return _sanitize_task_response(safe)

    # Fallback to DB
    result = await db.execute(
        select(TaskModel).where(TaskModel.id == task_id, TaskModel.user_id == user.id)
    )
    db_task = result.scalar_one_or_none()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    resp = {
        "task_id": db_task.id,
        "status": db_task.status,
        "task_type": db_task.task_type,
        "params": db_task.params,
        "expression": db_task.expression,
        "result": db_task.result,
        "error": db_task.error,
    }
    # 迭代任务：把 result.candidates 提升到顶层，前端依赖此字段
    if db_task.status == "iteration_completed" and isinstance(db_task.result, dict):
        resp["candidates"] = db_task.result.get("candidates", [])
        resp["candidates_done"] = len(resp["candidates"])
        resp["candidates_total"] = len(resp["candidates"])
        resp["task_type"] = "iteration"
        resp["parent_task_id"] = db_task.result.get("parent_task_id")
    return _sanitize_task_response(resp)


@app.get("/api/v1/tasks/{task_id}/stream")
async def stream_task(task_id: str, request: Request):
    """SSE 实时推送任务状态变化，直到 completed/failed 后关闭连接。"""
    # Authenticate via query param (EventSource can't set headers)
    token = request.query_params.get("token")
    is_guest = False
    user_id: str | None = None

    if not token or token.startswith("guest_"):
        # Guest access — only allow access to guest tasks
        is_guest = True
        user_id = GUEST_USER_ID
    else:
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
                    safe = _sanitize_task_response(safe)
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
    direction: str | None = Field(None, description="迭代方向提示，如'加入量价信息'、'增加低波暴露'")


def _run_iteration_task(task_id: str, parent_task_id: str, user_id: str, n_candidates: int, direction: str | None = None):
    """Execute iteration in background thread."""
    task = _tasks.get(task_id)
    if not task:
        return

    # Pre-persist task record so report FK constraints pass
    if not task.get("is_guest"):
        try:
            _persist_task_to_db(task_id, user_id, task)
        except Exception:
            pass

    try:
        # 1. Read parent task result — memory first, then DB
        parent_task = _tasks.get(parent_task_id)
        if parent_task and parent_task.get("status") == "completed":
            parent_result = parent_task.get("result", {})
            parent_expression = parent_task.get("expression", "")
            parent_params = parent_result.get("params", {})
        else:
            # Fallback to DB for historical tasks (e.g. after server restart)
            async def _fetch_parent():
                from .db import _get_session_factory
                factory = _get_session_factory()
                async with factory() as session:
                    r = await session.execute(
                        select(TaskModel).where(TaskModel.id == parent_task_id)
                    )
                    return r.scalar_one_or_none()

            db_parent = None
            if _main_loop and _main_loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_fetch_parent(), _main_loop)
                try:
                    db_parent = future.result(timeout=10)
                except Exception as e:
                    logger.error(f"[{task_id}] fetch parent from DB failed: {e}")

            if not db_parent or db_parent.status != "completed":
                task["status"] = "failed"
                task["error"] = "父任务未完成或不存在"
                return

            parent_result = db_parent.result or {}
            parent_expression = db_parent.expression or ""
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

        # 3a. Enrich with fundamental data if parent expression uses fundamental vars
        from .fundamental_data import detect_fundamental_vars, FundamentalDataFetcher, enrich_with_fundamentals_rq
        fund_vars = detect_fundamental_vars(parent_expression)
        if fund_vars:
            logger.info(f"[{task_id}] iteration: enriching market_df with fundamentals: {fund_vars}")
            sd = parent_params.get("start_date", "2023-01-01")
            ed = parent_params.get("end_date", "2025-12-31")
            rq_result = enrich_with_fundamentals_rq(market_df, fund_vars, stock_codes, sd, ed)
            if rq_result is not None:
                market_df = rq_result
            else:
                fund_fetcher = FundamentalDataFetcher()
                non_div_vars = fund_vars - {"dividend_yield"}
                if non_div_vars:
                    qdf = fund_fetcher.fetch_fundamentals(stock_codes, sd, ed, non_div_vars)
                    if qdf is not None and len(qdf) > 0:
                        market_df = fund_fetcher.align_to_daily(qdf, market_df, non_div_vars)
                if "dividend_yield" in fund_vars:
                    div_df = fund_fetcher.fetch_dividend_data(stock_codes, sd, ed)
                    if div_df is not None and len(div_df) > 0:
                        market_df = fund_fetcher.align_dividends_to_daily(div_df, market_df)

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
            direction=direction,
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
        if not task.get("is_guest"):
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
    db: AsyncSession = Depends(get_db),
):
    """提交迭代优化任务，基于已完成的回测结果生成候选改进因子。"""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    user_id = str(user.id)

    # Validate parent task — check memory first, then DB
    parent_task = _tasks.get(task_id)
    if parent_task:
        if parent_task.get("user_id") != user_id:
            raise HTTPException(status_code=404, detail="Task not found")
        if parent_task.get("status") != "completed":
            raise HTTPException(status_code=400, detail="只能对已完成的任务进行迭代优化")
        parent_params = parent_task.get("result", {}).get("params", {})
        parent_expression = parent_task.get("expression")
    else:
        # Fallback to DB for historical tasks (e.g. after server restart)
        result = await db.execute(
            select(TaskModel).where(TaskModel.id == task_id, TaskModel.user_id == user.id)
        )
        db_task = result.scalar_one_or_none()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        if db_task.status != "completed":
            raise HTTPException(status_code=400, detail="只能对已完成的任务进行迭代优化")
        parent_params = (db_task.result or {}).get("params", {})
        parent_expression = db_task.expression

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
                **parent_params,
                "parent_task_id": task_id,
                "n_candidates": req.n_candidates,
            },
            "expression": parent_expression,
            "candidates": [],
            "candidates_done": 0,
            "candidates_total": req.n_candidates,
            "created_at": time.time(),
        }
    logger.info(f"iteration task {iter_task_id} created for parent {task_id}")

    thread = threading.Thread(
        target=_run_iteration_task,
        args=(iter_task_id, task_id, user_id, req.n_candidates, req.direction),
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
    """Send feedback to webhook (Feishu) as interactive card. Returns True on success."""
    import httpx

    user_email = feedback_data.get("user_email", "unknown")
    description = feedback_data.get("description", "")
    task_id = feedback_data.get("task_id", "")
    page_url = feedback_data.get("page_url", "")
    created_at = feedback_data.get("created_at", "")
    screenshot_url = feedback_data.get("screenshot_url", "")

    # Build card elements
    elements: list[dict] = [
        {
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "default",
            "columns": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"**用户**\n{user_email}"}}],
                },
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"**时间**\n{created_at}"}}],
                },
            ],
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**问题描述**\n{description}"},
        },
    ]

    # Optional fields
    extra_parts = []
    if task_id:
        extra_parts.append(f"**任务 ID:** `{task_id}`")
    if page_url:
        extra_parts.append(f"**页面:** {page_url}")
    if screenshot_url:
        extra_parts.append(f"**截图:** [查看截图]({screenshot_url})")
    if extra_parts:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(extra_parts)},
        })

    # Footer
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "QuantGPT Feedback Bot"}],
    })

    payload: dict = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "新用户反馈"},
                "template": "orange",
            },
            "elements": elements,
        },
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
                body = resp.json() if resp.text else {}
                if body.get("code", 0) != 0:
                    logger.warning(f"Webhook API error: {body}")
                    return False
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
            host = request.headers.get("host", "localhost:8003")
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

    # Send confirmation email (fire-and-forget)
    import asyncio
    from .email_service import send_feedback_received_email

    async def _safe_send():
        try:
            await send_feedback_received_email(user.email, feedback_id, req.description)
        except Exception as e:
            logger.warning(f"Failed to send feedback confirmation email to {user.email}: {e}")

    asyncio.create_task(_safe_send())

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


# ---- robots.txt (prevent crawlers from indexing API / strategy code) ----

_ROBOTS_TXT = """\
User-agent: *
Disallow: /api/
Disallow: /mcp/
Disallow: /mcp-sse/
Allow: /
"""


@app.get("/robots.txt")
async def robots_txt():
    return HTMLResponse(content=_ROBOTS_TXT, media_type="text/plain")


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


# ---- Mount MCP at /mcp (both streamable-http and SSE) ----
from .mcp_server import mcp as _mcp_server
_mcp_app = _mcp_server.streamable_http_app()
_mcp_sse_app = _mcp_server.sse_app()
app.mount("/mcp", _mcp_app)
app.mount("/mcp-sse", _mcp_sse_app)

# ---- Serve chart images for email reports ----
_CHARTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "charts"
_CHARTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/charts", StaticFiles(directory=str(_CHARTS_DIR)), name="charts")


@app.middleware("http")
async def _mcp_path_rewrite(request: Request, call_next):
    """Rewrite /mcp to /mcp/ internally so Starlette Mount matches."""
    if request.url.path == "/mcp":
        request.scope["path"] = "/mcp/"
    return await call_next(request)


_mount_spa()
