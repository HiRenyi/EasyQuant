"""WorldQuant BRAIN dollar-neutral portfolio simulation.

Simulates WQ BRAIN's evaluation methodology: continuous-weight
dollar-neutral long-short portfolio with WQ-aligned Sharpe, Turnover,
Returns, and Fitness calculations. Used to estimate whether a factor
would pass WQ BRAIN's IS (In-Sample) tests.
"""

import numpy as np
import pandas as pd


def wq_simulate(
    work_df: pd.DataFrame,
    rebalance_dates: list,
    trading_days_per_year: int = 252,
) -> dict:
    """Simulate WQ BRAIN dollar-neutral portfolio from factor values.

    Args:
        work_df: DataFrame with trade_date, stock_code, factor_value, daily_ret.
        rebalance_dates: Sorted list of rebalance dates.
        trading_days_per_year: 252 for A-shares.

    Returns:
        Dict with wq_sharpe, wq_turnover, wq_returns, wq_fitness,
        wq_max_weight, wq_rating, margin_bps, submittable,
        sub_universe, and wq_is_tests (D1 threshold checks).
    """
    empty = {
        "wq_sharpe": 0.0, "wq_turnover": 0.0, "wq_returns": 0.0,
        "wq_fitness": 0.0, "wq_max_weight": 0.0, "wq_rating": "Needs Improvement",
        "margin_bps": 0.0, "submittable": False,
        "sub_universe": {}, "wq_is_tests": {},
    }

    if len(rebalance_dates) < 2:
        return empty

    rebal_set = set(rebalance_dates)
    dates = sorted(work_df["trade_date"].unique())

    daily_pnl = []
    turnovers = []
    current_weights = None
    pending_weights = None
    prev_weights = None
    max_weight = 0.0

    for date in dates:
        day_data = work_df[work_df["trade_date"] == date]

        if pending_weights is not None:
            prev_weights = current_weights
            current_weights = pending_weights
            pending_weights = None

            if prev_weights is not None:
                all_stocks = prev_weights.index.union(current_weights.index)
                old_w = prev_weights.reindex(all_stocks, fill_value=0)
                new_w = current_weights.reindex(all_stocks, fill_value=0)
                turnovers.append(float((new_w - old_w).abs().sum() / 2))

        if date in rebal_set:
            factor_vals = day_data.set_index("stock_code")["factor_value"].dropna()
            if len(factor_vals) < 2:
                continue

            weights = factor_vals - factor_vals.mean()
            total_abs = weights.abs().sum()
            if total_abs < 1e-12:
                continue
            weights = weights / total_abs

            max_weight = max(max_weight, float(weights.abs().max()))
            pending_weights = weights

        if current_weights is None:
            continue

        returns = day_data.set_index("stock_code")["daily_ret"]
        aligned = current_weights.index.intersection(returns.index)
        if len(aligned) == 0:
            continue

        pnl = float((current_weights.loc[aligned] * returns.loc[aligned]).sum())
        daily_pnl.append(pnl)

    if len(daily_pnl) < 10:
        return empty

    pnl_series = np.array(daily_pnl)
    pnl_mean = float(np.mean(pnl_series))
    pnl_std = float(np.std(pnl_series, ddof=1))

    wq_sharpe = float(np.sqrt(trading_days_per_year) * pnl_mean / pnl_std) if pnl_std > 0 else 0.0

    n_trading_days = len(daily_pnl)
    total_turnover = sum(turnovers)
    wq_turnover = total_turnover / n_trading_days if n_trading_days > 0 else 0.0

    wq_returns = pnl_mean * trading_days_per_year / 0.5

    effective_turnover = max(wq_turnover, 0.125)
    wq_fitness = 0.0
    if wq_sharpe != 0:
        wq_fitness = float(wq_sharpe * np.sqrt(abs(wq_returns) / effective_turnover))

    wq_rating = _calc_wq_rating(wq_fitness)

    margin_bps = 0.0
    daily_turnover_annualized = wq_turnover * trading_days_per_year
    if daily_turnover_annualized > 0:
        margin_bps = wq_returns / daily_turnover_annualized * 10000

    sub_universe = _sub_universe_sharpe(work_df, rebalance_dates, trading_days_per_year)

    is_tests = _run_is_tests(wq_sharpe, wq_fitness, wq_returns, wq_turnover, max_weight, sub_universe)
    submittable = all(t["pass"] for t in is_tests.values())

    return {
        "wq_sharpe": round(wq_sharpe, 4),
        "wq_turnover": round(wq_turnover, 4),
        "wq_returns": round(wq_returns, 4),
        "wq_fitness": round(wq_fitness, 4),
        "wq_max_weight": round(max_weight, 4),
        "wq_rating": wq_rating,
        "margin_bps": round(margin_bps, 1),
        "submittable": submittable,
        "sub_universe": sub_universe,
        "wq_is_tests": is_tests,
    }


def _calc_wq_rating(fitness: float) -> str:
    """BRAIN's official fitness-based rating label."""
    if fitness >= 2.5:
        return "Spectacular"
    if fitness >= 1.5:
        return "Excellent"
    if fitness >= 1.0:
        return "Good"
    if fitness >= 0.5:
        return "Average"
    return "Needs Improvement"


def _sub_universe_sharpe(
    work_df: pd.DataFrame,
    rebalance_dates: list,
    trading_days_per_year: int = 252,
    seed: int = 42,
) -> dict:
    """Split stocks 50/50, compute dollar-neutral Sharpe on each half.

    BRAIN sub-universe test proxy: both halves must have positive Sharpe
    above a minimum threshold.
    """
    all_stocks = work_df["stock_code"].unique()
    if len(all_stocks) < 10:
        return {"sub_sharpe_min": 0.0, "threshold": 1.19, "pass": False}

    rng = np.random.RandomState(seed)
    shuffled = rng.permutation(all_stocks)
    mid = len(shuffled) // 2
    half_a = set(shuffled[:mid])
    half_b = set(shuffled[mid:])

    rebal_set = set(rebalance_dates)
    sharpes = []

    for stock_set in [half_a, half_b]:
        sub_df = work_df[work_df["stock_code"].isin(stock_set)]
        dates = sorted(sub_df["trade_date"].unique())
        current_weights = None
        pending_weights = None
        daily_pnl = []

        for date in dates:
            day_data = sub_df[sub_df["trade_date"] == date]

            if pending_weights is not None:
                current_weights = pending_weights
                pending_weights = None

            if date in rebal_set:
                factor_vals = day_data.set_index("stock_code")["factor_value"].dropna()
                if len(factor_vals) < 2:
                    continue
                weights = factor_vals - factor_vals.mean()
                total_abs = weights.abs().sum()
                if total_abs < 1e-12:
                    continue
                pending_weights = weights / total_abs

            if current_weights is None:
                continue

            returns = day_data.set_index("stock_code")["daily_ret"]
            aligned = current_weights.index.intersection(returns.index)
            if len(aligned) == 0:
                continue

            daily_pnl.append(float(
                (current_weights.loc[aligned] * returns.loc[aligned]).sum()
            ))

        if len(daily_pnl) < 10:
            sharpes.append(0.0)
            continue

        arr = np.array(daily_pnl)
        std = float(np.std(arr, ddof=1))
        sh = float(np.sqrt(trading_days_per_year) * np.mean(arr) / std) if std > 0 else 0.0
        sharpes.append(sh)

    min_sh = min(sharpes) if sharpes else 0.0
    threshold = float(np.sqrt(trading_days_per_year) * max(0.065, 0.5 * 0.15))

    return {
        "sub_sharpe_a": round(sharpes[0], 3) if len(sharpes) > 0 else 0.0,
        "sub_sharpe_b": round(sharpes[1], 3) if len(sharpes) > 1 else 0.0,
        "sub_sharpe_min": round(min_sh, 3),
        "threshold": round(threshold, 3),
        "pass": min_sh >= threshold,
    }


def _run_is_tests(
    sharpe: float, fitness: float, returns: float,
    turnover: float, max_weight: float, sub_universe: dict,
) -> dict:
    """Check WQ BRAIN D1 IS test thresholds."""
    return {
        "sharpe": {
            "value": round(sharpe, 4),
            "threshold": 1.625,
            "label": "Sharpe ≥ 1.625",
            "pass": sharpe >= 1.625,
        },
        "fitness": {
            "value": round(fitness, 4),
            "threshold": 1.0,
            "label": "Fitness ≥ 1.0",
            "pass": fitness >= 1.0,
        },
        "returns": {
            "value": round(returns, 4),
            "threshold": 0.063,
            "label": "Returns ≥ 6.3%",
            "pass": abs(returns) >= 0.063,
        },
        "turnover_range": {
            "value": round(turnover, 4),
            "threshold_min": 0.01,
            "threshold_max": 0.70,
            "label": "Turnover ∈ [1%, 70%]",
            "pass": 0.01 <= turnover <= 0.70,
        },
        "weight": {
            "value": round(max_weight, 4),
            "threshold": 0.10,
            "label": "Max Weight ≤ 10%",
            "pass": max_weight <= 0.10,
        },
        "sub_universe": {
            "value": round(sub_universe.get("sub_sharpe_min", 0.0), 4),
            "threshold": sub_universe.get("threshold", 1.19),
            "label": f"Sub-Universe Sharpe ≥ {sub_universe.get('threshold', 1.19):.2f}",
            "pass": sub_universe.get("pass", False),
        },
    }
