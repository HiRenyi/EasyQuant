"""Factor group backtest engine.

Splits stocks into quantile groups by factor value, computes equal-weighted
returns per group, and produces a long-short return series suitable for
QuantStats analysis.
"""

import logging
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from .expression_parser import parse_expression
from .market_data import MarketDataFetcher

logger = logging.getLogger(__name__)


def run_factor_backtest(
    market_df: pd.DataFrame,
    expression: str,
    n_groups: int = 5,
    holding_period: int = 5,
) -> Dict:
    """Run quantile group backtest on a factor expression.

    Args:
        market_df: DataFrame with columns trade_date, stock_code, open, high,
                   low, close, volume, amount, pct_change.
        expression: Factor expression string (e.g. "rank(close/ts_mean(close, 20))").
        n_groups: Number of quantile groups.
        holding_period: Forward return period in trading days.

    Returns:
        Dict with keys: ls_returns (Series), group_returns, long_short_sharpe,
        monotonicity_score, spread.
    """
    # 1. Parse expression → factor function
    factor_func = parse_expression(expression)

    # 2. Compute factor values per stock
    market_df = market_df.copy()
    market_df["trade_date"] = pd.to_datetime(market_df["trade_date"])
    market_df = market_df.sort_values(["stock_code", "trade_date"])

    factor_values = market_df.groupby("stock_code", group_keys=False).apply(
        lambda g: _safe_apply_factor(g, factor_func)
    )
    market_df["factor_value"] = factor_values

    # 3. Forward returns
    fetcher = MarketDataFetcher.__new__(MarketDataFetcher)
    market_df = fetcher.calculate_forward_returns(market_df, periods=[holding_period])
    ret_col = f"fwd_ret_{holding_period}d"

    # 4. Drop NaN rows
    work = market_df[["trade_date", "stock_code", "factor_value", ret_col]].dropna().copy()
    if len(work) < n_groups * 10:
        raise ValueError(f"Insufficient data after NaN removal: {len(work)} rows")

    # 5. Assign quantile groups per date
    def _assign_group(group_df: pd.DataFrame) -> pd.Series:
        try:
            return pd.qcut(group_df["factor_value"], q=n_groups, labels=False, duplicates="drop")
        except ValueError:
            return pd.Series(np.nan, index=group_df.index)

    work["_group"] = work.groupby("trade_date", group_keys=False).apply(_assign_group)
    work = work.dropna(subset=["_group"])
    work["_group"] = work["_group"].astype(int)

    if work["_group"].nunique() < 2:
        raise ValueError("Could not form enough quantile groups — factor may have too few distinct values")

    # 6. Per-period group returns (equal-weighted)
    period_group_ret = (
        work.groupby(["trade_date", "_group"])[ret_col]
        .mean()
        .unstack(fill_value=0)
    )

    actual_groups = sorted(period_group_ret.columns)
    top_g, bot_g = actual_groups[-1], actual_groups[0]

    # 7. Long-short series
    ls_series = period_group_ret[top_g] - period_group_ret[bot_g]
    ls_series.name = "long_short"
    ls_series.index = pd.to_datetime(ls_series.index)

    # 8. Metrics
    annualize = np.sqrt(252 / max(holding_period, 1))
    ls_mean, ls_std = ls_series.mean(), ls_series.std()
    ls_sharpe = float((ls_mean / ls_std * annualize) if ls_std > 0 else 0.0)

    group_means = [float(period_group_ret[g].mean()) for g in actual_groups]
    mono = _calc_monotonicity(group_means)

    group_ret_summary = {}
    for g in actual_groups:
        s = period_group_ret[g]
        std = s.std()
        group_ret_summary[int(g)] = {
            "group": f"G{int(g)+1}",
            "mean_return": float(s.mean()),
            "annual_return": float((1 + s.mean()) ** (252 / max(holding_period, 1)) - 1),
            "sharpe": float((s.mean() / std * annualize) if std > 0 else 0.0),
            "max_drawdown": float(_calc_max_drawdown(s)),
        }

    return {
        "ls_returns": ls_series,
        "group_returns": group_ret_summary,
        "long_short_sharpe": ls_sharpe,
        "monotonicity_score": float(mono),
        "spread": float(group_means[-1] - group_means[0]),
    }


def _safe_apply_factor(group_df: pd.DataFrame, factor_func) -> pd.Series:
    """Apply factor function to a single stock's data, returning NaN on error."""
    try:
        result = factor_func(group_df)
        if isinstance(result, pd.Series):
            result.index = group_df.index
        return result
    except Exception as e:
        logger.warning(f"Factor computation failed for stock: {e}")
        return pd.Series(np.nan, index=group_df.index)


def _calc_max_drawdown(returns: pd.Series) -> float:
    """Calculate max drawdown from a return series."""
    cumulative = (1 + returns).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    return float(drawdown.min()) if len(drawdown) > 0 else 0.0


def _calc_monotonicity(group_means: List[float]) -> float:
    """Spearman rank correlation between group index and mean return."""
    if len(group_means) < 3:
        return 0.0
    ranks = list(range(len(group_means)))
    corr, _ = sp_stats.spearmanr(ranks, group_means)
    return abs(corr) if not np.isnan(corr) else 0.0
