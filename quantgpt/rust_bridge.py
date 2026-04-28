"""Bridge between Python backtest flow and Rust quantgpt_engine.

When quantgpt_engine is installed, the Rust engine handles:
  - Expression evaluation (factor computation)
  - Performance metrics (Sharpe, Sortino, etc.)

Falls back to pure Python if the Rust module is not available.
"""

import logging
import os

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import quantgpt_engine as _engine
    RUST_AVAILABLE = True
    logger.info("Rust engine (quantgpt_engine) loaded")
except ImportError:
    _engine = None  # type: ignore[assignment]
    RUST_AVAILABLE = False

RUST_ENABLED = RUST_AVAILABLE and os.environ.get("QUANTGPT_RUST_ENGINE", "1").lower() in ("1", "true", "yes")


def eval_factor_expression(df: pd.DataFrame, expression: str) -> pd.Series:
    """Evaluate a factor expression on a market DataFrame using Rust.

    Falls back to Python expression_parser if Rust is unavailable.
    """
    if not RUST_ENABLED:
        from .expression_parser import parse_expression
        fn = parse_expression(expression)
        return fn(df)

    columns = {}
    for col in df.columns:
        if col in ("trade_date", "stock_code"):
            continue
        try:
            columns[col] = df[col].to_numpy(dtype=np.float64, na_value=np.nan)
        except (ValueError, TypeError):
            continue

    # Compute derived columns
    if "vwap" not in columns and "amount" in columns and "volume" in columns:
        vol = columns["volume"]
        amt = columns["amount"]
        with np.errstate(divide="ignore", invalid="ignore"):
            columns["vwap"] = np.where(vol > 0, amt / vol, columns.get("close", np.full(len(df), np.nan)))

    if "returns" not in columns and "close" in columns:
        close = columns["close"]
        ret = np.empty_like(close)
        ret[0] = np.nan
        ret[1:] = (close[1:] - close[:-1]) / close[:-1]
        columns["returns"] = ret

    # Build stock group offsets (data must be sorted by stock_code, trade_date)
    stock_offsets = []
    date_offsets = []

    if "stock_code" in df.columns:
        sc = df["stock_code"].values
        start = 0
        for i in range(1, len(sc)):
            if sc[i] != sc[start]:
                stock_offsets.append((start, i))
                start = i
        stock_offsets.append((start, len(sc)))

    if "trade_date" in df.columns:
        td = df["trade_date"].values
        start = 0
        for i in range(1, len(td)):
            if td[i] != td[start]:
                date_offsets.append((start, i))
                start = i
        date_offsets.append((start, len(td)))

    try:
        result = _engine.eval_expression(expression, columns, stock_offsets, date_offsets)
        return pd.Series(result, index=df.index, name="factor_value")
    except Exception as e:
        logger.warning(f"Rust eval_expression failed ({e}), falling back to Python")
        from .expression_parser import parse_expression
        fn = parse_expression(expression)
        return fn(df)


def compute_metrics_rust(daily_returns: pd.Series, periods_per_year: int = 252) -> dict:
    """Compute performance metrics using Rust engine."""
    if not RUST_ENABLED:
        return {}

    rets = daily_returns.to_numpy(dtype=np.float64, na_value=0.0)
    try:
        return dict(_engine.compute_metrics(rets, float(periods_per_year)))
    except Exception:
        return {}
