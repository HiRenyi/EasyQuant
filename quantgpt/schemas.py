"""Shared validation constants, Pydantic validators, and common data-fetching helpers.

Centralises universe / date / benchmark validation so route modules
can import instead of re-defining.
"""

import re
from datetime import datetime

# ---- Constants ----

VALID_UNIVERSES = {"small_scale", "hs300", "csi500", "csi1000", "csi2000"}
VALID_BENCHMARKS = {"hs300", "zz500", "csi1000", "sz50"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---- Reusable Pydantic validators ----
# Usage:  _validate_date = field_validator("start_date", "end_date")(validate_date_format)
#         _validate_universe = field_validator("universe")(validate_universe_value)

def validate_date_format(cls, v: str) -> str:  # noqa: N805 (Pydantic convention)
    """Ensure date matches YYYY-MM-DD and is a real calendar date."""
    if not _DATE_RE.match(v):
        raise ValueError("日期格式必须为 YYYY-MM-DD")
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"无效日期: {v}")
    return v


def validate_universe_value(cls, v: str) -> str:  # noqa: N805
    if v not in VALID_UNIVERSES:
        raise ValueError(f"universe 必须是 {VALID_UNIVERSES} 之一")
    return v


def validate_benchmark_value(cls, v: str) -> str:  # noqa: N805
    if v not in VALID_BENCHMARKS:
        raise ValueError(f"benchmark 必须是 {VALID_BENCHMARKS} 之一")
    return v


# ---- Common data-fetching helper ----

def fetch_market_data(universe: str, start_date: str, end_date: str):
    """Fetch market data for the given universe and date range.

    Returns:
        (market_df, stock_codes) tuple.

    Raises:
        ValueError: If no data is fetched.
    """
    from .market_data import MarketDataFetcher, get_universe
    stock_codes = get_universe(universe, date=start_date)
    fetcher = MarketDataFetcher()
    market_df = fetcher.fetch_stocks(stock_codes, start_date, end_date)

    if market_df is None or len(market_df) == 0:
        raise ValueError("未获取到行情数据")
    return market_df, stock_codes
