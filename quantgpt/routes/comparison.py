"""Factor comparison API routes."""

import logging
import math

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator

from ..auth import get_current_user
from ..models import User
from ..schemas import validate_date_format, validate_universe_value, fetch_market_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["comparison"])


def _safe_float(v, default=0.0):
    """Convert value to JSON-safe float (replace NaN/Inf with default)."""
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return round(f, 6)
    except (TypeError, ValueError):
        return default


class CompareFactorItem(BaseModel):
    expression: str = Field(..., description="因子表达式")
    label: str | None = Field(None, description="因子标签")


class CompareFactorsRequest(BaseModel):
    factors: list[CompareFactorItem] = Field(..., min_length=2, max_length=6, description="待对比因子")
    universe: str = Field("hs300")
    start_date: str = Field("2023-01-01")
    end_date: str = Field("2025-12-31")
    n_groups: int = Field(5, ge=2, le=20)
    holding_period: int = Field(5, ge=1, le=60)

    _validate_universe = field_validator("universe")(validate_universe_value)
    _validate_dates = field_validator("start_date", "end_date")(validate_date_format)


@router.post("/compare-factors")
async def compare_factors(
    req: CompareFactorsRequest,
    user: User = Depends(get_current_user),
):
    """对比多个因子的回测表现。

    返回各因子的核心指标 + 相关性矩阵 + Top组逐日累计收益序列。
    """
    from ..backtest import run_factor_backtest, api_context
    from ..task_executor import get_executor, _run_backtest_in_process
    from ..composite import compute_factor_correlation

    # 1. Fetch data once
    try:
        market_df, stock_codes = fetch_market_data(req.universe, req.start_date, req.end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Enrich with fundamentals if any factor uses fundamental vars
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

    # 2. Run backtest for each factor
    results = []
    for f in req.factors:
        label = f.label or f.expression[:40]
        try:
            executor = get_executor()
            future = executor.submit_cpu_work(
                _run_backtest_in_process, market_df, f.expression, req.n_groups, req.holding_period,
            )
            bt = future.result(timeout=300)
            # Extract top-group cumulative returns as list
            cum_ret = (1 + bt["strategy_returns"]).cumprod()
            cum_ret_list = [
                {"date": str(d.date()) if hasattr(d, "date") else str(d)[:10], "value": _safe_float(v)}
                for d, v in cum_ret.items()
            ]

            results.append({
                "expression": f.expression,
                "label": label,
                "status": "success",
                "metrics": {
                    "sharpe": _safe_float(bt.get("top_group_sharpe", 0)),
                    "ls_sharpe": _safe_float(bt.get("long_short_sharpe", 0)),
                    "annual_return": _safe_float(bt.get("long_short_annual", 0)),
                    "monotonicity": _safe_float(bt.get("monotonicity_score", 0)),
                    "spread": _safe_float(bt.get("spread", 0)),
                    "ic_mean": _safe_float(bt.get("ic_mean", 0)),
                    "rank_ic_mean": _safe_float(bt.get("rank_ic_mean", 0)),
                    "ic_ir": _safe_float(bt.get("ic_ir", 0)),
                    "turnover": _safe_float(bt.get("turnover", 0)),
                },
                "cumulative_returns": cum_ret_list,
            })
        except Exception as e:
            logger.warning(f"Compare factor failed: {f.expression}: {e}")
            results.append({
                "expression": f.expression,
                "label": label,
                "status": "failed",
                "error": str(e),
            })

    # 3. Compute factor correlation
    valid_factors = [
        {"expression": f.expression, "label": f.label or f.expression[:40]}
        for f in req.factors
    ]
    correlation = None
    try:
        correlation = compute_factor_correlation(market_df, valid_factors)
    except Exception as e:
        logger.warning(f"Factor correlation failed: {e}")

    return {
        "factors": results,
        "correlation": correlation,
        "params": {
            "universe": req.universe,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "n_groups": req.n_groups,
            "holding_period": req.holding_period,
        },
    }
