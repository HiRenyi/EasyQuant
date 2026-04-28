"""Factor signal computation — dataclass, helpers, and cross-sectional analysis."""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .expression_parser import parse_expression

logger = logging.getLogger(__name__)


def json_default(obj):
    """Convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def sanitize_for_json(obj):
    """Recursively replace NaN/Inf with None for JSON compatibility."""
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    return obj


@dataclass
class FactorSignal:
    factor_id: str
    factor_name: str
    category: str
    signal_description: str
    direction: str          # "转强" | "转弱" | "持平"
    dispersion: str         # "高分化" | "中等" | "低分化"
    top_stocks: list        # [(code, value), ...]
    bottom_stocks: list     # [(code, value), ...]
    today_mean: float
    yesterday_mean: float
    # Percentile stats for compliant reporting
    pct_above_median: float  # % of stocks above cross-sectional median
    top10_pct_change: float  # avg change of top 10% vs yesterday
    # Historical context (20-day rolling window)
    percentile_20d: float   # today's mean percentile among recent 20-day means (0-100)
    zscore_20d: float       # (today_mean - 20d_mean_avg) / 20d_mean_std
    signal_strength: int    # -2 to +2 composite: direction + percentile


def safe_apply_factor(df: pd.DataFrame, factor_func) -> pd.Series:
    """Apply factor function to a DataFrame, returning NaN on error."""
    try:
        result = factor_func(df)
        if isinstance(result, pd.Series):
            result.index = df.index
        return result
    except Exception:
        return pd.Series(np.nan, index=df.index)


def strip_outer_rank(expression: str) -> str:
    """Remove outer rank() wrapper from expression for signal analysis.

    rank() normalizes values to [0, 1] percentiles, making cross-sectional
    means ~0.5 every day. For day-over-day signal detection we need raw values.
    Examples:
        "rank(close/ts_mean(close,20))" -> "close/ts_mean(close,20)"
        "rank(-1 * x) - rank(y)"        -> "rank(-1 * x) - rank(y)"  (not simple wrapper)
    """
    stripped = expression.strip()
    if not stripped.startswith("rank("):
        return expression
    # Check if the entire expression is rank(...) by matching parentheses
    depth = 0
    for i, ch in enumerate(stripped):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                # If we're at the end, the whole thing is rank(...)
                if i == len(stripped) - 1:
                    return stripped[5:i]  # strip "rank(" and ")"
                else:
                    return expression  # rank(...) is only part of expr
    return expression


def compute_factor_signals(
    market_df: pd.DataFrame,
    templates: list,
) -> list[FactorSignal]:
    """Compute factor signals for each template on today's market data.

    Requires market_df to have at least 70 days of history for time-series
    operators. Extracts today vs yesterday cross-sectional stats.
    """
    market_df = market_df.copy()
    market_df["trade_date"] = pd.to_datetime(market_df["trade_date"])
    market_df = market_df.sort_values(["stock_code", "trade_date"])

    all_dates = sorted(market_df["trade_date"].unique())
    if len(all_dates) < 2:
        logger.warning("Not enough trading days for factor signal computation")
        return []

    today = all_dates[-1]
    yesterday = all_dates[-2]

    signals = []
    for tmpl in templates:
        try:
            # Strip outer rank() for signal analysis — rank() normalizes to
            # ~0.5 mean every day, hiding real cross-sectional changes.
            # Raw factor values are needed to detect day-over-day shifts.
            expr = tmpl["expression"]
            raw_expr = strip_outer_rank(expr)
            factor_func = parse_expression(raw_expr)
            market_df["_fv"] = safe_apply_factor(market_df, factor_func)

            # Today's cross-section
            today_mask = market_df["trade_date"] == today
            today_df = market_df.loc[today_mask, ["stock_code", "_fv"]].dropna(subset=["_fv"])

            yesterday_mask = market_df["trade_date"] == yesterday
            yesterday_df = market_df.loc[yesterday_mask, ["stock_code", "_fv"]].dropna(subset=["_fv"])

            if len(today_df) < 10 or len(yesterday_df) < 10:
                continue

            today_mean = float(today_df["_fv"].mean())
            yesterday_mean = float(yesterday_df["_fv"].mean())
            today_std = float(today_df["_fv"].std())
            today_median = float(today_df["_fv"].median())

            # Direction
            delta = today_mean - yesterday_mean
            threshold = 0.05 * today_std if today_std > 0 else 0.001
            if delta > threshold:
                direction = "转强"
            elif delta < -threshold:
                direction = "转弱"
            else:
                direction = "持平"

            # Dispersion — compare today's cross-sectional std to recent average
            # Also collect daily cross-sectional means for percentile/z-score
            recent_stds = []
            recent_means = []
            for d in all_dates[-20:]:
                d_mask = market_df["trade_date"] == d
                d_vals = market_df.loc[d_mask, "_fv"].dropna()
                d_std = d_vals.std()
                d_mean = d_vals.mean()
                if not np.isnan(d_std):
                    recent_stds.append(d_std)
                if not np.isnan(d_mean):
                    recent_means.append(float(d_mean))
            avg_std = np.mean(recent_stds) if recent_stds else today_std
            if avg_std > 0 and today_std > 1.2 * avg_std:
                dispersion = "高分化"
            elif avg_std > 0 and today_std < 0.8 * avg_std:
                dispersion = "低分化"
            else:
                dispersion = "中等"

            # 20-day percentile and z-score of today's cross-sectional mean
            if len(recent_means) >= 3:
                mean_arr = np.array(recent_means)
                mean_avg = float(np.mean(mean_arr))
                mean_std = float(np.std(mean_arr, ddof=1))
                # Percentile: fraction of historical means <= today_mean
                percentile_20d = round(float(np.sum(mean_arr <= today_mean) / len(mean_arr)) * 100, 1)
                zscore_20d = round((today_mean - mean_avg) / mean_std, 2) if mean_std > 0 else 0.0
            else:
                percentile_20d = 50.0
                zscore_20d = 0.0

            # Signal strength: composite of direction + percentile
            if direction == "转强":
                signal_strength = 2 if percentile_20d >= 75 else 1
            elif direction == "转弱":
                signal_strength = -2 if percentile_20d <= 25 else -1
            else:
                signal_strength = 0

            # Percentile stats for compliant reporting
            pct_above_median = round(float((today_df["_fv"] > today_median).mean()) * 100, 1)

            # Top 10% group average change
            n_top = max(1, len(today_df) // 10)
            sorted_today = today_df.sort_values("_fv", ascending=False)
            top_codes = set(sorted_today.head(n_top)["stock_code"])
            top_today_avg = sorted_today.head(n_top)["_fv"].mean()
            top_yest = yesterday_df[yesterday_df["stock_code"].isin(top_codes)]["_fv"].mean()
            top10_pct_change = round(float(top_today_avg - top_yest), 4) if not np.isnan(top_yest) else 0.0

            # Top / bottom stocks (for signal cards, not for LLM)
            top_stocks = [
                (row["stock_code"], round(float(row["_fv"]), 4))
                for _, row in sorted_today.head(3).iterrows()
            ]
            bottom_stocks = [
                (row["stock_code"], round(float(row["_fv"]), 4))
                for _, row in sorted_today.tail(3).iterrows()
            ]

            signals.append(FactorSignal(
                factor_id=tmpl["id"],
                factor_name=tmpl["name"],
                category=tmpl["category"],
                signal_description=tmpl.get("signal_description", ""),
                direction=direction,
                dispersion=dispersion,
                top_stocks=top_stocks,
                bottom_stocks=bottom_stocks,
                today_mean=round(today_mean, 6),
                yesterday_mean=round(yesterday_mean, 6),
                pct_above_median=pct_above_median,
                top10_pct_change=top10_pct_change,
                percentile_20d=percentile_20d,
                zscore_20d=zscore_20d,
                signal_strength=signal_strength,
            ))
        except Exception as e:
            logger.warning(f"Factor signal computation failed for {tmpl['id']}: {e}")

    # Clean up temp column
    if "_fv" in market_df.columns:
        market_df.drop(columns=["_fv"], inplace=True)

    return signals
