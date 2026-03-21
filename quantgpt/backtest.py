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
    cost_rate: float = 0.003,
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
        cost_rate: Single rebalance cost rate (default 0.3% = commission + stamp tax + slippage).

    Returns:
        Dict with keys: strategy_returns (daily Series), group_returns,
        top_group_sharpe, monotonicity_score, spread, cost_adjusted, etc.
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
    use_value_grouping = False
    use_rank_fallback = False
    distinct_counts = work.groupby("trade_date")["factor_value"].nunique()
    median_distinct = int(distinct_counts.median()) if len(distinct_counts) > 0 else 0

    if median_distinct < n_groups:
        if median_distinct >= 2:
            effective_groups = median_distinct
            use_value_grouping = True
            logger.warning(
                f"Factor has only ~{median_distinct} distinct values per date, "
                f"reducing groups from {n_groups} to {effective_groups}, using value-based grouping"
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
        if use_value_grouping:
            # For few distinct values, group directly by sorted unique values
            sorted_uniques = sorted(vals.dropna().unique())
            if len(sorted_uniques) < 2:
                return pd.Series(np.nan, index=vals.index)
            mapping = {v: i for i, v in enumerate(sorted_uniques)}
            return vals.map(mapping)
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
    # Vectorized: build a lookup DataFrame indexed by (trade_date, stock_code)
    group_lookup = rebal_data.set_index(["trade_date", "stock_code"])["_group"]

    rebalance_dates_set = sorted(set(rebal_data["trade_date"].unique()))
    if len(rebalance_dates_set) < 2:
        raise ValueError("Not enough rebalance dates for backtest")

    # Build efficient lookup: for each date, find the most recent rebalance date
    # Use side="left" so that on the rebalance date T itself, the lookup returns
    # the *previous* rebalance date. This ensures the new grouping only takes
    # effect from T+1 onward, avoiding look-ahead bias (factor computed at T close
    # → position entered at T+1 open → T+1 return is the first attributed).
    rebal_arr = np.array(rebalance_dates_set, dtype="datetime64[ns]")

    # Vectorized searchsorted instead of per-row apply
    trade_dates = work["trade_date"].values.astype("datetime64[ns]")
    indices = np.searchsorted(rebal_arr, trade_dates, side="left") - 1
    valid_mask = indices >= 0
    work = work[valid_mask].copy()
    work["_rebal_date"] = rebal_arr[indices[valid_mask]]
    work = work.dropna(subset=["daily_ret"])

    # Vectorized merge instead of per-row dict lookup
    work = work.merge(
        group_lookup.rename("_group"),
        left_on=["_rebal_date", "stock_code"],
        right_index=True,
        how="left",
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

    # 6a. Transaction cost deduction
    cost_adjusted = False
    total_cost_drag = 0.0
    if cost_rate > 0:
        per_group_turnover = _calc_per_group_turnover(work, rebalance_dates_set, len(actual_groups))
        # For each group, on the first trading day after each rebalance, deduct turnover * cost_rate
        for g in actual_groups:
            if g not in per_group_turnover or per_group_turnover[g].empty:
                continue
            for rebal_date, turnover_val in per_group_turnover[g].items():
                if turnover_val <= 0:
                    continue
                cost = turnover_val * cost_rate
                # Find the first trading day AFTER rebal_date in daily_group_ret
                future_dates = daily_group_ret.index[daily_group_ret.index > rebal_date]
                if len(future_dates) > 0:
                    first_day = future_dates[0]
                    daily_group_ret.loc[first_day, g] -= cost
                    total_cost_drag += cost
        cost_adjusted = True

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
    ls_annual = float((1 + ls_mean) ** 252 - 1)

    group_means = [float(daily_group_ret[g].mean()) for g in actual_groups]
    mono = _calc_monotonicity(group_means)

    # If flipped, reverse group_means for spread calculation so spread is always positive
    spread = float(group_means[-1] - group_means[0])
    if flipped:
        spread = -spread

    # 9. IC / Rank IC / IR / IC win rate
    ic_series, rank_ic_series = _calc_ic_series(work, holding_period)
    ic_mean = float(ic_series.mean()) if len(ic_series) > 0 else 0.0
    ic_std = float(ic_series.std()) if len(ic_series) > 0 else 0.0
    ic_ir = float(ic_mean / ic_std) if ic_std > 0 else 0.0
    ic_win_rate = float((ic_series > 0).sum() / len(ic_series)) if len(ic_series) > 0 else 0.0
    rank_ic_mean = float(rank_ic_series.mean()) if len(rank_ic_series) > 0 else 0.0

    # 10. Turnover rate
    turnover = _calc_turnover(work, top_g, rebalance_dates_set)

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

    # 11. Stock factor data — extract latest rebalance factor values + period returns
    stock_factor_data = None
    if len(rebalance_dates_set) > 0:
        last_rebal = rebalance_dates_set[-1]
        last_rebal_data = rebal_data[rebal_data["trade_date"] == last_rebal].copy()
        if not last_rebal_data.empty:
            # Percentile rank: high rank = stronger signal (direction-aware)
            last_rebal_data["factor_rank"] = last_rebal_data["factor_value"].rank(
                ascending=(not flipped), pct=True
            )
            # Per-stock cumulative return over the backtest period (vectorized)
            period_ret_by_stock = (
                work.groupby("stock_code")["daily_ret"]
                .agg(lambda s: float((1 + s).prod() - 1))
            )
            stocks_list = []
            for _, row in last_rebal_data.sort_values("factor_rank", ascending=False).iterrows():
                g_idx = int(row["_group"])
                sc = row["stock_code"]
                stocks_list.append({
                    "stock_code": sc,
                    "factor_value": round(float(row["factor_value"]), 6),
                    "factor_rank": round(float(row["factor_rank"]), 4),
                    "group": g_idx,
                    "group_label": f"G{g_idx + 1}",
                    "period_return": round(float(period_ret_by_stock.get(sc, 0.0)), 6),
                })
            stock_factor_data = {
                "rebalance_date": str(last_rebal.date()) if hasattr(last_rebal, 'date') else str(last_rebal)[:10],
                "flipped": flipped,
                "total_stock_count": len(last_rebal_data),
                "stocks": stocks_list,
            }

    return {
        "strategy_returns": strategy_series,
        "ls_returns": ls_series,  # kept for backward compat
        "group_returns": group_ret_summary,
        "long_short_sharpe": ls_sharpe,
        "long_short_annual": ls_annual,
        "top_group_sharpe": top_sharpe,
        "monotonicity_score": float(mono),
        "spread": spread,
        "flipped": flipped,
        "ic_mean": ic_mean,
        "rank_ic_mean": rank_ic_mean,
        "ic_ir": ic_ir,
        "ic_win_rate": ic_win_rate,
        "turnover": turnover,
        "cost_adjusted": cost_adjusted,
        "cost_rate": cost_rate,
        "total_cost_drag": round(total_cost_drag, 6),
        "_factor_df": work[["trade_date", "stock_code", "factor_value", "daily_ret"]].copy(),
        "_stock_factor_data": stock_factor_data,
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


def _calc_ic_series(
    work: pd.DataFrame, holding_period: int
) -> tuple:
    """Calculate per-period IC and Rank IC series.

    IC = Pearson correlation between factor value and forward N-day return
    Rank IC = Spearman rank correlation (more robust to outliers)

    Returns (ic_series, rank_ic_series) as pd.Series indexed by date.
    """
    # Compute forward N-day return per stock
    # For day T: fwd_ret = ret[T+1] + ret[T+2] + ... + ret[T+holding_period]
    work = work.copy()
    work = work.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)
    shifted = work.groupby("stock_code")["daily_ret"].shift(-1)
    rolled = shifted.groupby(work["stock_code"]).rolling(
        holding_period, min_periods=holding_period
    ).sum()
    # rolling produces MultiIndex (stock_code, orig_index), extract orig_index level
    rolled = rolled.droplevel(0)
    work["fwd_ret"] = rolled.groupby(work["stock_code"]).shift(-(holding_period - 1))

    valid = work.dropna(subset=["factor_value", "fwd_ret"])
    if valid.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    def _pearson(g):
        if len(g) < 5:
            return np.nan
        fv = g["factor_value"]
        fr = g["fwd_ret"]
        if fv.nunique() < 2 or fr.nunique() < 2:
            return np.nan
        return fv.corr(fr)

    def _spearman(g):
        if len(g) < 5:
            return np.nan
        fv = g["factor_value"]
        fr = g["fwd_ret"]
        if fv.nunique() < 2 or fr.nunique() < 2:
            return np.nan
        corr, _ = sp_stats.spearmanr(fv.values, fr.values)
        return corr if not np.isnan(corr) else 0.0

    # Subsample dates for large datasets to avoid O(N*M) slowness
    all_ic_dates = sorted(valid["trade_date"].unique())
    if len(all_ic_dates) > 300:
        step = max(1, len(all_ic_dates) // 300)
        sampled_dates = set(all_ic_dates[::step])
        valid = valid[valid["trade_date"].isin(sampled_dates)]

    ic_series = valid.groupby("trade_date")[["factor_value", "fwd_ret"]].apply(_pearson).dropna()
    rank_ic_series = valid.groupby("trade_date")[["factor_value", "fwd_ret"]].apply(_spearman).dropna()
    return ic_series, rank_ic_series


def _calc_turnover(
    work: pd.DataFrame, top_group: int, rebalance_dates: list
) -> float:
    """Calculate average turnover rate for the top group.

    Turnover = fraction of holdings that change at each rebalance.
    """
    if len(rebalance_dates) < 2:
        return 0.0

    top_holdings = {}
    for d in rebalance_dates:
        day_data = work[(work["_rebal_date"] == d) & (work["_group"] == top_group)]
        top_holdings[d] = set(day_data["stock_code"].unique())

    turnovers = []
    sorted_dates = sorted(top_holdings.keys())
    for i in range(1, len(sorted_dates)):
        prev = top_holdings[sorted_dates[i - 1]]
        curr = top_holdings[sorted_dates[i]]
        if len(prev) == 0 and len(curr) == 0:
            continue
        union = prev | curr
        changed = len(prev.symmetric_difference(curr))
        turnovers.append(changed / len(union) if len(union) > 0 else 0.0)

    return float(np.mean(turnovers)) if turnovers else 0.0


def _calc_monotonicity(group_means: List[float]) -> float:
    """Spearman rank correlation between group index and mean return."""
    if len(group_means) < 3:
        return 0.0
    ranks = list(range(len(group_means)))
    corr, _ = sp_stats.spearmanr(ranks, group_means)
    return abs(corr) if not np.isnan(corr) else 0.0


def _calc_per_group_turnover(
    work: pd.DataFrame,
    rebalance_dates: list,
    n_groups: int,
) -> Dict[int, pd.Series]:
    """Calculate turnover per group on each rebalance date.

    Returns:
        Dict mapping group_id -> Series indexed by rebalance_date with turnover values.
    """
    # Build holdings per (rebal_date, group)
    holdings: Dict[tuple, set] = {}
    for d in rebalance_dates:
        for g in range(n_groups):
            day_data = work[(work["_rebal_date"] == d) & (work["_group"] == g)]
            holdings[(d, g)] = set(day_data["stock_code"].unique())

    sorted_dates = sorted(set(d for d, _ in holdings.keys()))
    result = {}
    for g in range(n_groups):
        turnovers = {}
        for i in range(1, len(sorted_dates)):
            prev = holdings.get((sorted_dates[i - 1], g), set())
            curr = holdings.get((sorted_dates[i], g), set())
            if len(prev) == 0 and len(curr) == 0:
                turnovers[sorted_dates[i]] = 0.0
                continue
            union = prev | curr
            changed = len(prev.symmetric_difference(curr))
            turnovers[sorted_dates[i]] = changed / len(union) if len(union) > 0 else 0.0
        result[g] = pd.Series(turnovers, dtype=float)
    return result
