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
        trading_days_per_year: 252 for A-shares, 365 for crypto.

    Returns:
        Dict with wq_sharpe, wq_turnover, wq_returns, wq_fitness,
        wq_max_weight, and wq_is_tests (D1 threshold checks).
    """
    empty = {
        "wq_sharpe": 0.0, "wq_turnover": 0.0, "wq_returns": 0.0,
        "wq_fitness": 0.0, "wq_max_weight": 0.0, "wq_is_tests": {},
    }

    if len(rebalance_dates) < 2:
        return empty

    rebal_set = set(rebalance_dates)
    dates = sorted(work_df["trade_date"].unique())

    daily_pnl = []
    turnovers = []
    current_weights = None
    prev_weights = None
    max_weight = 0.0

    for date in dates:
        day_data = work_df[work_df["trade_date"] == date]

        if date in rebal_set:
            factor_vals = day_data.set_index("stock_code")["factor_value"].dropna()
            if len(factor_vals) < 2:
                continue

            weights = factor_vals - factor_vals.mean()
            total_abs = weights.abs().sum()
            if total_abs < 1e-12:
                continue
            weights = weights / total_abs

            prev_weights = current_weights
            current_weights = weights

            max_weight = max(max_weight, float(weights.abs().max()))

            if prev_weights is not None:
                all_stocks = prev_weights.index.union(current_weights.index)
                old_w = prev_weights.reindex(all_stocks, fill_value=0)
                new_w = current_weights.reindex(all_stocks, fill_value=0)
                turnovers.append(float((new_w - old_w).abs().sum() / 2))

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

    is_tests = _run_is_tests(wq_sharpe, wq_fitness, wq_returns, wq_turnover, max_weight)

    return {
        "wq_sharpe": round(wq_sharpe, 4),
        "wq_turnover": round(wq_turnover, 4),
        "wq_returns": round(wq_returns, 4),
        "wq_fitness": round(wq_fitness, 4),
        "wq_max_weight": round(max_weight, 4),
        "wq_is_tests": is_tests,
    }


def _run_is_tests(
    sharpe: float, fitness: float, returns: float,
    turnover: float, max_weight: float,
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
    }
