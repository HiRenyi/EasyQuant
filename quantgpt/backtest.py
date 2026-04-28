"""Factor group backtest engine (long-only, A-share).

Splits stocks into quantile groups by factor value on rebalance dates,
holds each group for holding_period days, computes daily equal-weighted
returns per group. The strategy return is the top group's daily return.
"""

import logging
import threading

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from .expression_parser import parse_expression
from .wq_simulate import wq_simulate

logger = logging.getLogger(__name__)

_api_context = threading.local()


def _require_api_context():
    if not getattr(_api_context, "active", False):
        raise RuntimeError(
            "run_factor_backtest must be called through the API task system. "
            "Direct calls are forbidden. Submit via /api/v1/auto_backtest."
        )


def enable_api_context():
    _api_context.active = True


def disable_api_context():
    _api_context.active = False


from contextlib import contextmanager


@contextmanager
def api_context():
    enable_api_context()
    try:
        yield
    finally:
        disable_api_context()


def run_factor_backtest(
    market_df: pd.DataFrame,
    expression: str | None = None,
    n_groups: int = 5,
    holding_period: int = 5,
    cost_rate: float = 0.003,
    neutralize_industry: bool = True,
    neutralize_cap: bool = True,
    precomputed_factor: pd.Series | None = None,
    trading_days_per_year: int = 252,
) -> dict:
    """Run quantile group backtest on a factor expression (long-only).

    IMPORTANT: Must be called through API task system. Direct calls raise RuntimeError.

    Strategy: on each rebalance date (every holding_period trading days),
    rank all stocks by factor value, split into n_groups quantile groups,
    hold each group until next rebalance. Report daily returns for each group.

    The "strategy" return series is the top group (highest factor values).

    Args:
        market_df: DataFrame with columns trade_date, stock_code, open, high,
                   low, close, volume, amount, pct_change.
        expression: Factor expression string. Can be None if precomputed_factor is provided.
        n_groups: Number of quantile groups.
        holding_period: Days between rebalances.
        cost_rate: Single rebalance cost rate (default 0.3% = commission + stamp tax + slippage).
        precomputed_factor: Pre-computed factor values (Series indexed like market_df).
                           If provided, expression is ignored.

    Returns:
        Dict with keys: strategy_returns (daily Series), group_returns,
        top_group_sharpe, monotonicity_score, spread, cost_adjusted, etc.
    """
    _require_api_context()

    # 1. Compute factor values
    market_df = market_df.copy()
    market_df["trade_date"] = pd.to_datetime(market_df["trade_date"])
    market_df = market_df.sort_values(["stock_code", "trade_date"])

    if precomputed_factor is not None:
        market_df["factor_value"] = precomputed_factor.values if hasattr(precomputed_factor, 'values') else precomputed_factor
    elif expression is not None:
        from .rust_bridge import RUST_ENABLED, eval_factor_expression
        if RUST_ENABLED:
            market_df["factor_value"] = eval_factor_expression(market_df, expression)
        else:
            factor_func = parse_expression(expression)
            market_df["factor_value"] = _safe_apply_factor(market_df, factor_func)
    else:
        raise ValueError("必须提供 expression 或 precomputed_factor")

    # Save raw factor values for IC computation (before neutralization).
    # IC should be computed on raw values (industry standard), while group
    # formation uses neutralized values to control sector/cap risk.
    raw_factor_for_ic = market_df["factor_value"].copy()

    # 1b. Neutralize factor values (optional)
    if neutralize_industry or neutralize_cap:
        from .neutralize import neutralize_factor
        market_df["factor_value"] = neutralize_factor(
            market_df["factor_value"],
            market_df,
            industry=neutralize_industry,
            market_cap=neutralize_cap,
        )

    # 3. Compute daily returns from close prices (T-1 close → T close)
    market_df["daily_ret"] = market_df.groupby("stock_code")["close"].pct_change()

    # 4. Identify rebalance dates
    all_dates = sorted(market_df["trade_date"].unique())
    rebalance_dates = all_dates[::holding_period]

    # 5. On each rebalance date, assign groups based on factor value
    #    Build a mapping: (trade_date, stock_code) -> group
    work = market_df[["trade_date", "stock_code", "factor_value", "daily_ret", "close"]].dropna(
        subset=["factor_value"]
    ).copy()

    # Determine grouping strategy: rank-based by default (aligned with WQ BRAIN)
    effective_groups = n_groups
    use_value_grouping = False
    distinct_counts = work.groupby("trade_date")["factor_value"].nunique()
    median_distinct = int(distinct_counts.median()) if len(distinct_counts) > 0 else 0

    if median_distinct < n_groups and median_distinct >= 2:
        effective_groups = median_distinct
        use_value_grouping = True
        logger.warning(
            f"Factor has only ~{median_distinct} distinct values per date, "
            f"reducing groups from {n_groups} to {effective_groups}, using value-based grouping"
        )

    def _assign_group(vals: pd.Series) -> pd.Series:
        if use_value_grouping:
            sorted_uniques = sorted(vals.dropna().unique())
            if len(sorted_uniques) < 2:
                return pd.Series(np.nan, index=vals.index)
            mapping = {v: i for i, v in enumerate(sorted_uniques)}
            return vals.map(mapping)
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
    annualize = np.sqrt(trading_days_per_year)
    strat_mean, strat_std = strategy_series.mean(), strategy_series.std()
    top_sharpe = float((strat_mean / strat_std * annualize) if strat_std > 0 else 0.0)

    ls_mean, ls_std = ls_series.mean(), ls_series.std()
    ls_sharpe = float((ls_mean / ls_std * annualize) if ls_std > 0 else 0.0)
    ls_annual = float((1 + ls_mean) ** trading_days_per_year - 1)

    group_means = [float(daily_group_ret[g].mean()) for g in actual_groups]
    mono = _calc_monotonicity(group_means)

    # If flipped, reverse group_means for spread calculation so spread is always positive
    spread = float(group_means[-1] - group_means[0])
    if flipped:
        spread = -spread

    # 9. IC / Rank IC / IR / IC win rate
    # Use raw (pre-neutralization) factor values for IC — industry standard.
    # Neutralization is for portfolio construction only, not IC measurement.
    # Primary IC metric is Rank IC (Spearman) — more robust to outliers,
    # consistent with industry convention (聚宽, Barra, ai-quant, etc.).
    work_ic = work.copy()
    work_ic["factor_value"] = raw_factor_for_ic.reindex(work_ic.index)
    pearson_ic_series, rank_ic_series = _calc_ic_series(work_ic, holding_period)
    # Main IC metrics use Rank IC (Spearman)
    ic_mean = float(rank_ic_series.mean()) if len(rank_ic_series) > 0 else 0.0
    ic_std = float(rank_ic_series.std()) if len(rank_ic_series) > 0 else 0.0
    ic_ir = float(ic_mean / ic_std) if ic_std > 0 else 0.0
    ic_win_rate = float((rank_ic_series > 0).sum() / len(rank_ic_series)) if len(rank_ic_series) > 0 else 0.0
    rank_ic_mean = ic_mean  # same as ic_mean now (both Spearman)

    # 10. Turnover rate (daily, WQ BRAIN-aligned)
    turnover = _calc_turnover(work, top_g, rebalance_dates_set, holding_period)

    group_ret_summary = {}
    for g in actual_groups:
        s = daily_group_ret[g]
        std = s.std()
        group_ret_summary[int(g)] = {
            "group": f"G{int(g)+1}",
            "mean_return": float(s.mean()),
            "annual_return": float((1 + s.mean()) ** trading_days_per_year - 1),
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

    # 12. WorldQuant Fitness (approx, based on group backtest metrics)
    wq_fitness = 0.0
    if ls_sharpe != 0 and turnover > 0:
        effective_turnover = max(turnover, 0.125)
        wq_fitness = float(ls_sharpe * np.sqrt(abs(ls_annual) / effective_turnover))

    # 13. WQ BRAIN dollar-neutral simulation (continuous weights, WQ-aligned metrics)
    wq_work = work[["trade_date", "stock_code", "factor_value", "daily_ret"]].copy()
    if flipped:
        wq_work["factor_value"] = -wq_work["factor_value"]
    wq_brain = wq_simulate(wq_work, rebalance_dates_set, trading_days_per_year)

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
        "wq_fitness": round(wq_fitness, 4),
        "wq_brain": wq_brain,
        "cost_adjusted": cost_adjusted,
        "cost_rate": cost_rate,
        "total_cost_drag": round(total_cost_drag, 6),
        "_factor_df": work[["trade_date", "stock_code", "factor_value", "daily_ret"]].copy(),
        "_stock_factor_data": stock_factor_data,
    }


def _safe_apply_factor(df: pd.DataFrame, factor_func) -> pd.Series:
    """Apply factor function to a DataFrame, returning NaN on error."""
    try:
        result = factor_func(df)
        if isinstance(result, pd.Series):
            result.index = df.index
        return result
    except Exception as e:
        logger.warning(f"Factor computation failed: {e}")
        return pd.Series(np.nan, index=df.index)


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
    # For day T: fwd_ret = (close[T+N] - close[T]) / close[T]
    # Using pct_change(N).shift(-N) for clean, industry-standard forward returns.
    work = work.copy()
    work = work.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)
    work["fwd_ret"] = (
        work.groupby("stock_code")["close"]
        .pct_change(holding_period)
        .shift(-holding_period)
    )

    valid = work.dropna(subset=["factor_value", "fwd_ret"])
    if valid.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    def _pearson(g):
        if len(g) < 10:
            return np.nan
        fv = g["factor_value"]
        fr = g["fwd_ret"]
        if fv.nunique() < 2 or fr.nunique() < 2:
            return np.nan
        return fv.corr(fr)

    def _spearman(g):
        if len(g) < 10:
            return np.nan
        fv = g["factor_value"]
        fr = g["fwd_ret"]
        if fv.nunique() < 2 or fr.nunique() < 2:
            return np.nan
        corr, _ = sp_stats.spearmanr(fv.values, fr.values)
        return corr if not np.isnan(corr) else 0.0

    ic_series = valid.groupby("trade_date")[["factor_value", "fwd_ret"]].apply(_pearson).dropna()
    rank_ic_series = valid.groupby("trade_date")[["factor_value", "fwd_ret"]].apply(_spearman).dropna()
    return ic_series, rank_ic_series


def _calc_turnover(
    work: pd.DataFrame, top_group: int, rebalance_dates: list,
    holding_period: int = 1,
) -> float:
    """Calculate average daily turnover for the top group (WQ BRAIN-aligned).

    Per-rebalance turnover = (entering + exiting) / avg_portfolio_size.
    Daily turnover = per_rebalance / holding_period.
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
        avg_size = (len(prev) + len(curr)) / 2
        if avg_size == 0:
            continue
        entering = len(curr - prev)
        exiting = len(prev - curr)
        turnovers.append((entering + exiting) / avg_size)

    per_rebal = float(np.mean(turnovers)) if turnovers else 0.0
    return per_rebal / holding_period


def _calc_monotonicity(group_means: list[float]) -> float:
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
) -> dict[int, pd.Series]:
    """Calculate turnover per group on each rebalance date.

    Returns:
        Dict mapping group_id -> Series indexed by rebalance_date with turnover values.
    """
    # Build holdings per (rebal_date, group)
    holdings: dict[tuple, set] = {}
    for d in rebalance_dates:
        for g in range(n_groups):
            day_data = work[(work["_rebal_date"] == d) & (work["_group"] == g)]
            holdings[(d, g)] = set(day_data["stock_code"].unique())

    sorted_dates = sorted(set(d for d, _ in holdings))
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
