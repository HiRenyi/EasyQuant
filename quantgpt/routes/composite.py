"""Composite (multi-factor) backtest API routes."""

import logging
import time
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field, field_validator

from ..auth import get_current_user
from ..models import User
from ..schemas import validate_date_format, validate_universe_value, fetch_market_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["composite"])


class FactorItem(BaseModel):
    expression: str = Field(..., description="因子表达式")
    weight: float = Field(1.0, ge=0, le=10, description="权重")
    label: str | None = Field(None, description="因子标签")


class CompositeBacktestRequest(BaseModel):
    factors: list[FactorItem] = Field(..., min_length=2, max_length=10, description="因子列表")
    combination_method: str = Field("weighted_rank", description="组合方式: weighted_rank / weighted_zscore / equal_weight")
    universe: str = Field("hs300", description="股票池")
    start_date: str = Field("2023-01-01")
    end_date: str = Field("2025-12-31")
    n_groups: int = Field(5, ge=2, le=20)
    holding_period: int = Field(5, ge=1, le=60)
    benchmark: str = Field("hs300")
    session_id: str | None = Field(None)

    @field_validator("combination_method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        valid = {"weighted_rank", "weighted_zscore", "equal_weight"}
        if v not in valid:
            raise ValueError(f"combination_method 必须是 {valid} 之一")
        return v

    _validate_universe = field_validator("universe")(validate_universe_value)
    _validate_dates = field_validator("start_date", "end_date")(validate_date_format)


class CorrelationRequest(BaseModel):
    factors: list[FactorItem] = Field(..., min_length=2, max_length=10)
    universe: str = Field("hs300")
    start_date: str = Field("2023-01-01")
    end_date: str = Field("2025-12-31")

    _validate_universe = field_validator("universe")(validate_universe_value)
    _validate_dates = field_validator("start_date", "end_date")(validate_date_format)


class AttributionRequest(BaseModel):
    factors: list[FactorItem] = Field(..., min_length=2, max_length=10, description="子因子列表")
    composite_expression: str | None = Field(None, description="组合因子表达式（可选）")
    universe: str = Field("hs300")
    start_date: str = Field("2023-01-01")
    end_date: str = Field("2025-12-31")
    n_groups: int = Field(5, ge=2, le=20)
    holding_period: int = Field(5, ge=1, le=60)

    _validate_universe = field_validator("universe")(validate_universe_value)
    _validate_dates = field_validator("start_date", "end_date")(validate_date_format)


@router.post("/composite-backtest", status_code=202)
async def composite_backtest(
    req: CompositeBacktestRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """提交多因子组合回测任务。"""
    from ..api_server import (
        _check_rate_limit, _active_task_count, _cleanup_tasks,
        _tasks, _tasks_lock, MAX_ACTIVE_TASKS,
    )

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    if _active_task_count() >= MAX_ACTIVE_TASKS:
        raise HTTPException(status_code=503, detail="当前回测任务已满，请稍后再试")

    _cleanup_tasks()

    task_id = uuid.uuid4().hex[:12]
    user_id = str(user.id)
    factors_list = [f.model_dump() for f in req.factors]

    with _tasks_lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "session_id": req.session_id,
            "status": "pending",
            "task_type": "composite",
            "params": {
                "factors": factors_list,
                "combination_method": req.combination_method,
                "universe": req.universe,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "n_groups": req.n_groups,
                "holding_period": req.holding_period,
                "benchmark": req.benchmark,
            },
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_composite_task,
        args=(task_id, req, user_id),
        daemon=True,
    )
    thread.start()

    return {"task_id": task_id, "status": "pending"}


def _run_composite_task(task_id: str, req: CompositeBacktestRequest, user_id: str):
    """Background worker for composite backtest."""
    import traceback
    from ..api_server import _tasks, _persist_task_to_db, _cleanup_reports
    from ..market_data import fetch_benchmark_returns
    from ..composite import run_composite_backtest
    from ..report import generate_report

    task = _tasks.get(task_id)
    if not task:
        return

    report_filename = None
    try:
        task["status"] = "fetching_data"
        try:
            market_df, stock_codes = fetch_market_data(req.universe, req.start_date, req.end_date)
        except ValueError as e:
            task["status"] = "failed"
            task["error"] = str(e)
            return

        # Enrich with fundamental data if any factor uses fundamental vars
        from ..fundamental_data import detect_fundamental_vars, FundamentalDataFetcher, enrich_with_fundamentals_rq
        all_fund_vars: set[str] = set()
        for f in req.factors:
            all_fund_vars |= detect_fundamental_vars(f.expression)
        if all_fund_vars:
            task["status"] = "fetching_fundamentals"
            logger.info(f"[{task_id}] composite: enriching with fundamentals: {all_fund_vars}")
            rq_result = enrich_with_fundamentals_rq(market_df, all_fund_vars, stock_codes, req.start_date, req.end_date)
            if rq_result is not None:
                market_df = rq_result
            else:
                fetcher = FundamentalDataFetcher()
                non_div = all_fund_vars - {"dividend_yield"}
                if non_div:
                    qdf = fetcher.fetch_fundamentals(stock_codes, req.start_date, req.end_date, non_div)
                    if qdf is not None and len(qdf) > 0:
                        market_df = fetcher.align_to_daily(qdf, market_df, non_div)
                if "dividend_yield" in all_fund_vars:
                    div_df = fetcher.fetch_dividend_data(stock_codes, req.start_date, req.end_date)
                    if div_df is not None and len(div_df) > 0:
                        market_df = fetcher.align_dividends_to_daily(div_df, market_df)

        task["status"] = "backtesting"
        factors_list = [f.model_dump() for f in req.factors]
        result = run_composite_backtest(
            market_df=market_df,
            factors=factors_list,
            method=req.combination_method,
            n_groups=req.n_groups,
            holding_period=req.holding_period,
        )

        task["status"] = "generating_report"
        bm_returns = None
        try:
            bm_returns = fetch_benchmark_returns(req.benchmark, req.start_date, req.end_date)
        except Exception:
            pass

        user_report_dir = Path(__file__).resolve().parent.parent.parent / "reports" / user_id
        user_report_dir.mkdir(parents=True, exist_ok=True)

        report_result = generate_report(
            result["strategy_returns"],
            benchmark_returns=bm_returns,
            title="Composite Factor Backtest",
            output_dir=str(user_report_dir),
        )
        report_filename = Path(report_result["report_path"]).name

        composite_expr = result.get("composite_expression", "")
        task["expression"] = composite_expr
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
            },
            "correlation": result.get("correlation"),
            "params": {
                "expression": composite_expr,
                "factors": factors_list,
                "combination_method": req.combination_method,
                "universe": req.universe,
                "start_date": req.start_date,
                "end_date": req.end_date,
                "n_groups": req.n_groups,
                "holding_period": req.holding_period,
                "benchmark": req.benchmark,
                "stock_count": len(stock_codes),
            },
            "llm": {
                "prompt": f"多因子组合回测: {len(factors_list)}个因子",
                "generated_expression": composite_expr,
            },
        }
        _cleanup_reports(user_id)

    except Exception as e:
        logger.error(f"[{task_id}] composite backtest failed: {traceback.format_exc()}")
        task["status"] = "failed"
        task["error"] = f"多因子组合回测失败: {str(e)}"
    finally:
        try:
            _persist_task_to_db(task_id, user_id, task, report_filename)
        except Exception as e:
            logger.error(f"[{task_id}] DB persist error: {e}")


@router.post("/factor-correlation")
async def factor_correlation(
    req: CorrelationRequest,
    user: User = Depends(get_current_user),
):
    """计算多因子间的相关性矩阵。"""
    from ..composite import compute_factor_correlation

    try:
        market_df, stock_codes = fetch_market_data(req.universe, req.start_date, req.end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Enrich with fundamentals if needed
    from ..fundamental_data import detect_fundamental_vars, FundamentalDataFetcher, enrich_with_fundamentals_rq
    all_fund_vars: set[str] = set()
    for f in req.factors:
        all_fund_vars |= detect_fundamental_vars(f.expression)
    if all_fund_vars:
        rq_result = enrich_with_fundamentals_rq(market_df, all_fund_vars, stock_codes, req.start_date, req.end_date)
        if rq_result is not None:
            market_df = rq_result
        else:
            fetcher = FundamentalDataFetcher()
            non_div = all_fund_vars - {"dividend_yield"}
            if non_div:
                qdf = fetcher.fetch_fundamentals(stock_codes, req.start_date, req.end_date, non_div)
                if qdf is not None and len(qdf) > 0:
                    market_df = fetcher.align_to_daily(qdf, market_df, non_div)

    factors_list = [f.model_dump() for f in req.factors]
    correlation = compute_factor_correlation(market_df, factors_list)
    return correlation


@router.post("/factor-attribution")
async def factor_attribution(
    req: AttributionRequest,
    user: User = Depends(get_current_user),
):
    """因子归因分解：分析各子因子对组合的贡献度。"""
    from ..attribution import compute_factor_attribution

    try:
        market_df, stock_codes = fetch_market_data(req.universe, req.start_date, req.end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Enrich with fundamentals if needed
    from ..fundamental_data import detect_fundamental_vars, FundamentalDataFetcher, enrich_with_fundamentals_rq
    all_fund_vars: set[str] = set()
    for f in req.factors:
        all_fund_vars |= detect_fundamental_vars(f.expression)
    if req.composite_expression:
        all_fund_vars |= detect_fundamental_vars(req.composite_expression)
    if all_fund_vars:
        rq_result = enrich_with_fundamentals_rq(market_df, all_fund_vars, stock_codes, req.start_date, req.end_date)
        if rq_result is not None:
            market_df = rq_result
        else:
            fetcher = FundamentalDataFetcher()
            non_div = all_fund_vars - {"dividend_yield"}
            if non_div:
                qdf = fetcher.fetch_fundamentals(stock_codes, req.start_date, req.end_date, non_div)
                if qdf is not None and len(qdf) > 0:
                    market_df = fetcher.align_to_daily(qdf, market_df, non_div)

    factors_list = [f.model_dump() for f in req.factors]
    result = compute_factor_attribution(
        market_df=market_df,
        sub_factors=factors_list,
        composite_expression=req.composite_expression,
        n_groups=req.n_groups,
        holding_period=req.holding_period,
    )
    return result
