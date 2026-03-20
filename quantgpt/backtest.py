"""Factor group backtest engine (long-only, A-share).

Splits stocks into quantile groups by factor value on rebalance dates,
holds each group for holding_period days, computes daily equal-weighted
returns per group. The strategy return is the top group's daily return.
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
    """Run quantile group backtest on a factor expression (long-only).

    Strategy: on each rebalance date (every holding_period trading days),
    rank all stocks by factor value, split into n_groups quantile groups,
    hold each group until next rebalance. Report daily returns for each group.

    The "strategy" return series is the top group (highest factor values).

    Args:
        market_df: DataFrame with columns trade_date, stock_code, open, high,
                   low, close, volume, amount, pct_change.
        expression: Factor expression string.
        n_groups: Number of quantile groups.
        holding_period: Days between rebalances.

    Returns:
        Dict with keys: strategy_returns (daily Series), group_returns,
        top_group_sharpe, monotonicity_score, spread.
    """
    # 1. Parse expression
    factor_func = parse_expression(expression)

    # 2. Compute factor values per stock
    market_df = market_df.copy()
    market_df["trade_date"] = pd.to_datetime(market_df["trade_date"])
    market_df = market_df.sort_values(["stock_code", "trade_date"])

    factor_values = market_df.groupby("stock_code", group_keys=False).apply(
        lambda g: _safe_apply_factor(g, factor_func)
    )
    market_df["factor_value"] = factor_values

    # 3. Compute daily returns from close prices (T-1 close → T close)
    market_df["daily_ret"] = market_df.groupby("stock_code")["close"].pct_change()

    # 4. Identify rebalance dates
    all_dates = sorted(market_df["trade_date"].unique())
    rebalance_dates = all_dates[::holding_period]

    # 5. On each rebalance date, assign groups based on factor value
    #    Build a mapping: (trade_date, stock_code) -> group
    work = market_df[["trade_date", "stock_code", "factor_value", "daily_ret"]].dropna(
        subset=["factor_value"]
    ).copy()

    # Determine grouping strategy
    effective_groups = n_groups
    use_rank_fallback = False
    distinct_counts = work.groupby("trade_date")["factor_value"].nunique()
    median_distinct = int(distinct_counts.median()) if len(distinct_counts) > 0 else 0

    if median_distinct < n_groups:
        if median_distinct >= 2:
            effective_groups = median_distinct
            logger.warning(
                f"Factor has only ~{median_distinct} distinct values per date, "
                f"reducing groups from {n_groups} to {effective_groups}"
            )
        else:
            use_rank_fallback = True
            effective_groups = n_groups
            logger.warning(
                f"Factor has ~{median_distinct} distinct value(s) per date, "
                f"falling back to rank-based grouping"
            )

    def _assign_group(vals: pd.Series) -> pd.Series:
        if use_rank_fallback:
            try:
                ranks = vals.rank(method="first")
                return pd.cut(ranks, bins=effective_groups, labels=False)
            except ValueError:
                return pd.Series(np.nan, index=vals.index)
        try:
            return pd.qcut(vals, q=effective_groups, labels=False, duplicates="drop")
        except ValueError:
            try:
                ranks = vals.rank(method="first")
                return pd.cut(ranks, bins=effective_groups, labels=False)
            except ValueError:
                return pd.Series(np.nan, index=vals.index)

    # Assign groups only on rebalance dates, then forward-fill to holding period
    rebal_data = work[work["trade_date"].isin(rebalance_dates)].copy()
    rebal_data["_group"] = rebal_data.groupby("trade_date")["factor_value"].transform(_assign_group)
    rebal_data = rebal_data.dropna(subset=["_group"])
    rebal_data["_group"] = rebal_data["_group"].astype(int)

    # Build stock->group assignment that persists from rebalance to next rebalance
    # For each stock, create a time series of group assignments
    group_assignments = {}  # {(rebal_date, stock_code): group}
    for _, row in rebal_data[["trade_date", "stock_code", "_group"]].iterrows():
        group_assignments[(row["trade_date"], row["stock_code"])] = row["_group"]

    # For every trading day, look up which group each stock belongs to
    # based on the most recent rebalance date
    rebalance_dates_set = sorted(set(rebal_data["trade_date"].unique()))
    if len(rebalance_dates_set) < 2:
        raise ValueError("Not enough rebalance dates for backtest")

    # Build efficient lookup: for each date, find the most recent rebalance date
    # Use side="left" so that on the rebalance date T itself, the lookup returns
    # the *previous* rebalance date. This ensures the new grouping only takes
    # effect from T+1 onward, avoiding look-ahead bias (factor computed at T close
    # → position entered at T+1 open → T+1 return is the first attributed).
    rebal_arr = np.array(rebalance_dates_set)

    def _get_rebal_date(d):
        idx = np.searchsorted(rebal_arr, d, side="left") - 1
        return rebal_arr[idx] if idx >= 0 else None

    work["_rebal_date"] = work["trade_date"].apply(_get_rebal_date)
    work = work.dropna(subset=["_rebal_date", "daily_ret"])

    # Look up group assignment from the rebalance date
    work["_group"] = work.apply(
        lambda r: group_assignments.get((r["_rebal_date"], r["stock_code"]), np.nan),
        axis=1,
    )
    work = work.dropna(subset=["_group"])
    work["_group"] = work["_group"].astype(int)

    if work["_group"].nunique() < 2:
        raise ValueError("Could not form enough quantile groups")

    # 6. Daily equal-weighted group returns
    daily_group_ret = (
        work.groupby(["trade_date", "_group"])["daily_ret"]
        .mean()
        .unstack(fill_value=0)
    )

    actual_groups = sorted(daily_group_ret.columns)
    top_g = actual_groups[-1]
    bot_g = actual_groups[0]

    # Auto-detect factor direction: if bottom group outperforms top group,
    # flip the labeling so "top" always means the best-performing group.
    top_mean = daily_group_ret[top_g].mean()
    bot_mean = daily_group_ret[bot_g].mean()
    flipped = False
    if bot_mean > top_mean:
        flipped = True
        top_g, bot_g = bot_g, top_g
        logger.info("Factor direction flipped: low factor values outperform high values")

    # 7. Strategy = best-performing group (long-only, A-share)
    strategy_series = daily_group_ret[top_g].copy()
    strategy_series.name = "strategy"
    strategy_series.index = pd.to_datetime(strategy_series.index)

    # Also compute long-short for metrics (informational only)
    ls_series = daily_group_ret[top_g] - daily_group_ret[bot_g]

    # 8. Metrics
    annualize = np.sqrt(252)
    strat_mean, strat_std = strategy_series.mean(), strategy_series.std()
    top_sharpe = float((strat_mean / strat_std * annualize) if strat_std > 0 else 0.0)

    ls_mean, ls_std = ls_series.mean(), ls_series.std()
    ls_sharpe = float((ls_mean / ls_std * annualize) if ls_std > 0 else 0.0)

    group_means = [float(daily_group_ret[g].mean()) for g in actual_groups]
    mono = _calc_monotonicity(group_means)

    # If flipped, reverse group_means for spread calculation so spread is always positive
    spread = float(group_means[-1] - group_means[0])
    if flipped:
        spread = -spread

    group_ret_summary = {}
    for g in actual_groups:
        s = daily_group_ret[g]
        std = s.std()
        group_ret_summary[int(g)] = {
            "group": f"G{int(g)+1}",
            "mean_return": float(s.mean()),
            "annual_return": float((1 + s.mean()) ** 252 - 1),
            "sharpe": float((s.mean() / std * annualize) if std > 0 else 0.0),
            "max_drawdown": float(_calc_max_drawdown(s)),
        }

    return {
        "strategy_returns": strategy_series,
        "ls_returns": ls_series,  # kept for backward compat
        "group_returns": group_ret_summary,
        "long_short_sharpe": ls_sharpe,
        "top_group_sharpe": top_sharpe,
        "monotonicity_score": float(mono),
        "spread": spread,
        "flipped": flipped,
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
