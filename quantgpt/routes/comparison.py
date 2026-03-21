"""Factor comparison API routes."""

import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator

from ..auth import get_current_user
from ..models import User
from ..schemas import validate_date_format, validate_universe_value, fetch_market_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["comparison"])


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
    from ..backtest import run_factor_backtest
    from ..composite import compute_factor_correlation

    # 1. Fetch data once
    try:
        market_df, _ = fetch_market_data(req.universe, req.start_date, req.end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Run backtest for each factor
    results = []
    for f in req.factors:
        label = f.label or f.expression[:40]
        try:
            bt = run_factor_backtest(
                market_df, f.expression, req.n_groups, req.holding_period
            )
            # Extract top-group cumulative returns as list
            cum_ret = (1 + bt["strategy_returns"]).cumprod()
            cum_ret_list = [
                {"date": str(d.date()) if hasattr(d, "date") else str(d)[:10], "value": round(float(v), 4)}
                for d, v in cum_ret.items()
            ]

            results.append({
                "expression": f.expression,
                "label": label,
                "status": "success",
                "metrics": {
                    "sharpe": bt.get("top_group_sharpe", 0),
                    "ls_sharpe": bt["long_short_sharpe"],
                    "annual_return": bt.get("long_short_annual", 0),
                    "monotonicity": bt["monotonicity_score"],
                    "spread": bt["spread"],
                    "ic_mean": bt.get("ic_mean", 0),
                    "rank_ic_mean": bt.get("rank_ic_mean", 0),
                    "ic_ir": bt.get("ic_ir", 0),
                    "turnover": bt.get("turnover", 0),
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
