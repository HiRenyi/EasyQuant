"""Composite (multi-factor) combination engine.

Combines multiple factor expressions into a single composite factor value,
then delegates to the standard run_factor_backtest for group backtest.
"""

import logging
from typing import Dict, List, Literal

import pandas as pd

from .expression_parser import parse_expression
from .backtest import run_factor_backtest, _safe_apply_factor, api_context
from .task_executor import get_executor, _run_backtest_precomputed_in_process

logger = logging.getLogger(__name__)

CombineMethod = Literal["weighted_rank", "weighted_zscore", "equal_weight"]


def combine_factors(
    market_df: pd.DataFrame,
    factors: List[Dict],
    method: CombineMethod = "weighted_rank",
) -> pd.Series:
    """Compute composite factor values from multiple expressions.

    Args:
        market_df: Market data DataFrame (trade_date, stock_code, OHLCV...).
        factors: List of {"expression": str, "weight": float}.
        method: Combination method.

    Returns:
        Series of composite factor values, indexed like market_df.
    """
    df = market_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["stock_code", "trade_date"])

    factor_cols = []
    weights = []

    for i, f in enumerate(factors):
        expr = f["expression"]
        w = f.get("weight", 1.0)
        col_name = f"_factor_{i}"

        func = parse_expression(expr)
        df[col_name] = _safe_apply_factor(df, func)
        factor_cols.append(col_name)
        weights.append(w)

    # Normalize weights
    total_w = sum(weights)
    if total_w <= 0:
        total_w = len(weights)
        weights = [1.0] * len(weights)
    norm_weights = [w / total_w for w in weights]

    if method == "equal_weight":
        norm_weights = [1.0 / len(factors)] * len(factors)

    # Cross-sectional transform per date, then combine
    def _combine_date(group: pd.DataFrame) -> pd.Series:
        composite = pd.Series(0.0, index=group.index)
        for col, w in zip(factor_cols, norm_weights):
            vals = group[col]
            if vals.isna().all():
                continue
            if method == "weighted_rank" or method == "equal_weight":
                transformed = vals.rank(pct=True)
            elif method == "weighted_zscore":
                mean = vals.mean()
                std = vals.std()
                transformed = (vals - mean) / std if std > 0 else vals * 0
            else:
                transformed = vals.rank(pct=True)
            composite += w * transformed.fillna(0)
        return composite

    df["_composite"] = df.groupby("trade_date", group_keys=False).apply(
        lambda g: _combine_date(g)
    )
    return df["_composite"]


def compute_factor_correlation(
    market_df: pd.DataFrame,
    factors: List[Dict],
) -> Dict:
    """Compute pairwise IC correlation matrix between factors.

    Returns:
        Dict with "matrix" (list of lists), "labels" (factor names/expressions).
    """
    df = market_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["stock_code", "trade_date"])

    labels = []
    factor_cols = []

    for i, f in enumerate(factors):
        expr = f["expression"]
        col_name = f"_factor_{i}"
        labels.append(f.get("label", expr[:40]))

        func = parse_expression(expr)
        df[col_name] = _safe_apply_factor(df, func)
        factor_cols.append(col_name)

    # Cross-sectional rank per date, then compute correlation
    for col in factor_cols:
        df[col + "_rank"] = df.groupby("trade_date")[col].rank(pct=True)

    rank_cols = [c + "_rank" for c in factor_cols]
    corr_df = df[rank_cols].corr()

    matrix = corr_df.values.tolist()
    return {
        "labels": labels,
        "matrix": [[round(v, 4) if not (isinstance(v, float) and (v != v or abs(v) == float("inf"))) else 0.0 for v in row] for row in matrix],
    }


def run_composite_backtest(
    market_df: pd.DataFrame,
    factors: List[Dict],
    method: CombineMethod = "weighted_rank",
    n_groups: int = 5,
    holding_period: int = 5,
    cost_rate: float = 0.003,
) -> Dict:
    """Run group backtest on a composite (multi-factor) signal.

    This computes the composite factor, injects it as a virtual expression,
    and delegates to run_factor_backtest.

    Args:
        market_df: Market DataFrame.
        factors: List of {"expression": str, "weight": float}.
        method: "weighted_rank" | "weighted_zscore" | "equal_weight".
        n_groups, holding_period, cost_rate: Backtest parameters.

    Returns:
        Same dict as run_factor_backtest, plus "correlation" and
        "composite_expression" fields.
    """
    # 1. Compute composite factor values
    composite_vals = combine_factors(market_df, factors, method)

    # 2. Inject composite values into market_df
    df = market_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["stock_code", "trade_date"])

    # 3. Build composite expression string for display
    parts = []
    for f in factors:
        w = f.get("weight", 1.0)
        expr = f["expression"]
        parts.append(f"{w:.2f} * rank({expr})")
    composite_expression = " + ".join(parts)

    # 4. Run backtest with pre-computed composite factor
    df = market_df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["stock_code", "trade_date"])

    executor = get_executor()
    future = executor.submit_cpu_work(
        _run_backtest_precomputed_in_process,
        df, n_groups, holding_period, cost_rate, composite_vals,
    )
    result = future.result(timeout=600)

    # 5. Compute factor correlation
    correlation = compute_factor_correlation(market_df, factors)

    result["correlation"] = correlation
    result["composite_expression"] = composite_expression
    result["factors"] = factors
    result["method"] = method

    return result
