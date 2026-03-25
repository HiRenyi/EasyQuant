"""Factor attribution — decompose composite factor returns into sub-factor contributions."""

import logging

import numpy as np
import pandas as pd

from .backtest import run_factor_backtest
from .expression_parser import parse_expression

logger = logging.getLogger(__name__)


def compute_factor_attribution(
    market_df: pd.DataFrame,
    sub_factors: list[dict],
    composite_expression: str | None = None,
    n_groups: int = 5,
    holding_period: int = 5,
) -> dict:
    """Decompose composite factor performance into sub-factor contributions.

    Args:
        market_df: Market data DataFrame with OHLCV columns.
        sub_factors: List of dicts with "expression" and optional "label".
        composite_expression: If provided, also backtest the composite.
        n_groups: Number of quantile groups.
        holding_period: Holding period in trading days.

    Returns:
        Dict with per-factor metrics, IC correlation matrix, and marginal contributions.
    """
    if len(sub_factors) < 2:
        raise ValueError("至少需要2个子因子进行归因分析")

    factor_results = []
    factor_ic_series = {}

    # 1. Backtest each sub-factor individually
    for i, sf in enumerate(sub_factors):
        expr = sf["expression"]
        label = sf.get("label", f"Factor_{i+1}")
        try:
            result = run_factor_backtest(market_df, expr, n_groups, holding_period)
            factor_results.append({
                "expression": expr,
                "label": label,
                "sharpe": result.get("long_short_sharpe", 0),
                "annual_return": result.get("long_short_annual", 0),
                "monotonicity": result.get("monotonicity_score", 0),
                "spread": result.get("spread", 0),
                "ic_mean": result.get("ic_mean", 0),
                "ic_ir": result.get("ic_ir", 0),
                "turnover": result.get("turnover", 0),
                "status": "success",
            })
            # Collect IC series for correlation
            ic_series = result.get("_ic_series")
            if ic_series is not None:
                factor_ic_series[label] = ic_series
        except Exception as e:
            logger.warning(f"Sub-factor backtest failed for {label}: {e}")
            factor_results.append({
                "expression": expr,
                "label": label,
                "status": "failed",
                "error": str(e),
            })

    # 2. Compute IC correlation matrix
    ic_correlation = None
    if len(factor_ic_series) >= 2:
        ic_df = pd.DataFrame(factor_ic_series)
        ic_correlation = {}
        corr_matrix = ic_df.corr()
        for label in corr_matrix.columns:
            ic_correlation[label] = {
                col: round(float(corr_matrix.loc[label, col]), 4)
                for col in corr_matrix.columns
            }

    # 3. Compute cross-sectional factor values for marginal contribution
    contributions = _compute_marginal_contributions(market_df, sub_factors, n_groups, holding_period)

    # 4. Composite backtest (if expression provided)
    composite_result = None
    if composite_expression:
        try:
            result = run_factor_backtest(market_df, composite_expression, n_groups, holding_period)
            composite_result = {
                "expression": composite_expression,
                "sharpe": result.get("long_short_sharpe", 0),
                "annual_return": result.get("long_short_annual", 0),
                "monotonicity": result.get("monotonicity_score", 0),
                "ic_mean": result.get("ic_mean", 0),
            }
        except Exception as e:
            logger.warning(f"Composite backtest failed: {e}")

    return {
        "factors": factor_results,
        "ic_correlation": ic_correlation,
        "contributions": contributions,
        "composite": composite_result,
    }


def _compute_marginal_contributions(
    market_df: pd.DataFrame,
    sub_factors: list[dict],
    n_groups: int,
    holding_period: int,
) -> list[dict]:
    """Estimate each factor's marginal contribution via leave-one-out IC drop."""
    if len(sub_factors) < 2:
        return []

    # Compute factor values for each sub-factor
    df_sorted = market_df.sort_values(["stock_code", "trade_date"]) if "stock_code" in market_df.columns else market_df.sort_values(["code", "trade_date"])
    stock_col = "stock_code" if "stock_code" in market_df.columns else "code"
    factor_values = {}
    for i, sf in enumerate(sub_factors):
        label = sf.get("label", f"Factor_{i+1}")
        try:
            func = parse_expression(sf["expression"])
            vals = func(df_sorted)
            if isinstance(vals, pd.Series):
                vals.index = df_sorted.index
            # Cross-sectional rank per date
            ranked = vals.groupby(df_sorted["trade_date"]).rank(pct=True)
            factor_values[label] = ranked
        except Exception:
            continue

    if len(factor_values) < 2:
        return []

    # Equal-weight composite IC
    labels = list(factor_values.keys())
    combined = sum(factor_values[l] for l in labels) / len(labels)

    # Forward returns for IC calculation
    fwd = market_df.groupby("code")["close"].pct_change(holding_period).shift(-holding_period)

    full_ic = _rank_ic(combined, fwd, market_df["trade_date"])

    contributions = []
    for label in labels:
        # Leave-one-out: composite without this factor
        remaining = [l for l in labels if l != label]
        if not remaining:
            contributions.append({"label": label, "marginal_ic": round(full_ic, 6)})
            continue
        partial = sum(factor_values[l] for l in remaining) / len(remaining)
        partial_ic = _rank_ic(partial, fwd, market_df["trade_date"])
        marginal = full_ic - partial_ic
        contributions.append({
            "label": label,
            "marginal_ic": round(marginal, 6),
            "contribution_pct": round(marginal / max(abs(full_ic), 1e-8) * 100, 1),
        })

    # Sort by absolute marginal contribution descending
    contributions.sort(key=lambda c: abs(c.get("marginal_ic", 0)), reverse=True)
    return contributions


def _rank_ic(factor_series: pd.Series, returns_series: pd.Series, date_series: pd.Series) -> float:
    """Compute mean cross-sectional rank IC."""
    df = pd.DataFrame({"factor": factor_series, "ret": returns_series, "date": date_series}).dropna()
    if len(df) == 0:
        return 0.0
    ics = df.groupby("date").apply(
        lambda g: g["factor"].corr(g["ret"], method="spearman") if len(g) > 5 else np.nan
    )
    return float(ics.dropna().mean()) if len(ics.dropna()) > 0 else 0.0
