"""Factor neutralization — QuantGPT
Copyright (c) 2026 Miasyster. Licensed under the MIT License.
https://github.com/Miasyster/QuantGPT

Removes systematic exposures (industry, market-cap) from factor values
before backtesting, so that the factor captures alpha rather than beta/style tilts.
"""

import logging
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Global lock for baostock
_bs_lock = threading.Lock()


def industry_neutralize(
    factor_df: pd.DataFrame,
    industry_col: str = "industry",
) -> pd.Series:
    """Industry-neutralize factor values (cross-sectional within each date).

    Subtracts industry mean from factor values → within-industry relative ranking.

    Args:
        factor_df: DataFrame with columns [trade_date, stock_code, factor_value, industry].
        industry_col: Column name for industry classification.

    Returns:
        Neutralized factor values as Series.
    """
    def _neutralize_date(group):
        fv = group["factor_value"]
        ind = group[industry_col]
        # Subtract industry mean
        ind_mean = fv.groupby(ind).transform("mean")
        return fv - ind_mean

    result = factor_df.groupby("trade_date", group_keys=False).apply(_neutralize_date)
    return result


def cap_neutralize(
    factor_df: pd.DataFrame,
    cap_col: str = "market_cap",
) -> pd.Series:
    """Market-cap neutralize factor values (cross-sectional regression residual).

    Regresses factor values on log(market_cap) per date, returns residuals.

    Args:
        factor_df: DataFrame with columns [trade_date, stock_code, factor_value, market_cap].
        cap_col: Column name for market capitalization.

    Returns:
        Neutralized factor values as Series (regression residuals).
    """
    def _neutralize_date(group):
        fv = group["factor_value"].values
        cap = group[cap_col].values
        # Log transform
        log_cap = np.log(cap + 1)
        # Simple OLS: factor = a + b * log_cap + residual
        valid = ~(np.isnan(fv) | np.isnan(log_cap) | (log_cap == 0))
        if valid.sum() < 5:
            return pd.Series(fv, index=group.index)
        X = np.column_stack([np.ones(valid.sum()), log_cap[valid]])
        y = fv[valid]
        try:
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            predicted = X @ beta
            residuals = np.full(len(fv), np.nan)
            residuals[valid] = y - predicted
            return pd.Series(residuals, index=group.index)
        except Exception:
            return pd.Series(fv, index=group.index)

    result = factor_df.groupby("trade_date", group_keys=False).apply(_neutralize_date)
    return result


def neutralize_factor(
    factor_values: pd.Series,
    market_df: pd.DataFrame,
    industry: bool = False,
    market_cap: bool = False,
) -> pd.Series:
    """Apply neutralization to factor values.

    Args:
        factor_values: Factor values (same index as market_df).
        market_df: Market data DataFrame.
        industry: Whether to apply industry neutralization.
        market_cap: Whether to apply market-cap neutralization.

    Returns:
        Neutralized factor values.
    """
    if not industry and not market_cap:
        return factor_values

    work = market_df[["trade_date", "stock_code"]].copy()
    work["factor_value"] = factor_values.values

    if industry:
        # Get industry data
        ind_data = get_industry_data(market_df["stock_code"].unique().tolist())
        if ind_data is not None and len(ind_data) > 0:
            work = work.merge(ind_data[["stock_code", "industry"]], on="stock_code", how="left")
            work["industry"] = work["industry"].fillna("其他")
            work["factor_value"] = industry_neutralize(work).values
            work = work.drop(columns=["industry"])
        else:
            logger.warning("Industry data not available, skipping industry neutralization")

    if market_cap:
        # Use close * volume as rough market cap proxy (actual cap data not available)
        work["market_cap"] = market_df["close"].values * market_df["volume"].values
        work["factor_value"] = cap_neutralize(work).values
        work = work.drop(columns=["market_cap"])

    return pd.Series(work["factor_value"].values, index=factor_values.index)


def get_industry_data(stock_codes: list) -> pd.DataFrame | None:
    """Get industry classification for stocks from baostock.

    Uses Shenwan Level-1 industry classification. Caches per month.
    """
    cache_dir = _PROJECT_ROOT / "data" / "industry"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Monthly cache
    month_key = time.strftime("%Y-%m")
    cache_path = cache_dir / f"industry_{month_key}.parquet"

    if cache_path.exists():
        try:
            df = pd.read_parquet(cache_path)
            if len(df) > 100:
                return df
        except Exception:
            pass

    # Fetch from baostock
    try:
        import baostock as bs
    except ImportError:
        logger.warning("baostock not installed, cannot fetch industry data")
        return None

    results = []
    with _bs_lock:
        try:
            lg = bs.login()
            if lg.error_code != "0":
                return None

            for code in stock_codes:
                try:
                    rs = bs.query_stock_industry(code=code)
                    while rs.error_code == "0" and rs.next():
                        row = rs.get_row_data()
                        if len(row) >= 4:
                            results.append({
                                "stock_code": row[1],
                                "industry": row[3],  # industry name
                                "industry_code": row[2] if len(row) > 2 else "",
                            })
                        break  # Only need one row per stock
                except Exception:
                    continue
        finally:
            try:
                bs.logout()
            except Exception:
                pass

    if not results:
        return None

    df = pd.DataFrame(results)
    try:
        df.to_parquet(cache_path, index=False)
    except Exception:
        pass

    logger.info(f"Fetched industry data for {len(df)} stocks")
    return df
