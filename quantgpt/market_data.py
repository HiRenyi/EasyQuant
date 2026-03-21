"""Simplified market data fetcher with baostock + Parquet caching."""

import os
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pathlib import Path

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Global lock for baostock — it only supports one session per process
_bs_lock = threading.Lock()

try:
    import baostock as bs
    HAS_BAOSTOCK = True
except ImportError:
    HAS_BAOSTOCK = False

# Project root for default paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

BENCHMARK_CODES = {
    "hs300": {"baostock": "sh.000300", "name": "沪深300"},
    "zz500": {"baostock": "sh.000905", "name": "中证500"},
    "csi500": {"baostock": "sh.000905", "name": "中证500"},  # alias
    "csi1000": {"baostock": "sh.000852", "name": "中证1000"},
    "sz50": {"baostock": "sh.000016", "name": "上证50"},
}

# Pre-defined stock universes
UNIVERSES = {
    "small_scale": [
        "sh.600519", "sh.601318", "sz.000858", "sz.000333", "sh.600036",
    ],
}

# --- PLACEHOLDER_MARKET_DATA ---


def _baostock_login():
    """Login to baostock, return True on success. Retries on network errors."""
    if not HAS_BAOSTOCK:
        raise RuntimeError("baostock is not installed")
    for attempt in range(3):
        try:
            lg = bs.login()
            if lg.error_code == "0":
                return True
            if attempt < 2:
                logger.warning(f"baostock login attempt {attempt+1} failed: {lg.error_msg}, retrying...")
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"baostock login failed: {lg.error_msg}")
        except RuntimeError:
            raise
        except Exception as e:
            if attempt < 2:
                logger.warning(f"baostock login attempt {attempt+1} error: {e}, retrying...")
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"baostock login error: {e}")
    return True


def _baostock_logout():
    try:
        bs.logout()
    except Exception:
        pass


def get_universe(name: str, date: Optional[str] = None) -> List[str]:
    """Return stock code list for a named universe.

    Supports: small_scale (static), hs300, csi500/zz500 (dynamic via baostock),
              csi1000 (derived: hs300+csi500 excluded from all A),
              full_a (all tradable A-share stocks).
    """
    if name in UNIVERSES:
        return UNIVERSES[name]

    if name in ("hs300", "csi500", "zz500"):
        return _fetch_index_constituents(name, date)

    if name == "csi1000":
        return _fetch_csi1000(date)

    if name == "full_a":
        return _fetch_full_a(date)

    raise ValueError(f"Unknown universe: {name}. Available: {list(UNIVERSES.keys()) + ['hs300', 'csi500', 'zz500', 'csi1000', 'full_a']}")


def _fetch_index_constituents(name: str, date: Optional[str] = None) -> List[str]:
    """Fetch index constituents from baostock."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    with _bs_lock:
        _baostock_login()
        try:
            if name == "hs300":
                rs = bs.query_hs300_stocks(date)
            else:  # csi500 / zz500
                rs = bs.query_zz500_stocks(date)

            codes = []
            while rs.error_code == "0" and rs.next():
                row = rs.get_row_data()
                codes.append(row[1])  # code column
            logger.info(f"Fetched {len(codes)} constituents for {name}")
            return codes
        finally:
            _baostock_logout()


def _fetch_csi1000(date: Optional[str] = None) -> List[str]:
    """Fetch CSI 1000 constituents (derived: all A - HS300 - CSI500).

    Since baostock has no direct CSI1000 API, we get all A-share stocks
    and exclude HS300 + CSI500 constituents, then take the top 1000 by
    average daily trading volume (proxy for liquidity/market-cap ranking).
    """
    date = date or datetime.now().strftime("%Y-%m-%d")

    # Cache path
    cache_dir = _PROJECT_ROOT / "data" / "universe"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"csi1000_{date[:7]}.txt"  # monthly cache

    if cache_path.exists():
        codes = cache_path.read_text().strip().split("\n")
        if len(codes) > 500:
            logger.info(f"CSI1000 loaded from cache: {len(codes)} stocks")
            return codes

    hs300 = set(_fetch_index_constituents("hs300", date))
    csi500 = set(_fetch_index_constituents("csi500", date))
    exclude = hs300 | csi500

    all_stocks = _fetch_all_stock_codes(date)
    remaining = [c for c in all_stocks if c not in exclude]

    # Take first 1000 (baostock returns them sorted by code; better would be
    # by market cap, but code order is a reasonable proxy for established stocks)
    result = remaining[:1000]
    logger.info(f"CSI1000 derived: {len(result)} stocks (all_a={len(all_stocks)}, excluded={len(exclude)})")

    cache_path.write_text("\n".join(result))
    return result


def _fetch_full_a(date: Optional[str] = None) -> List[str]:
    """Fetch all tradable A-share stock codes.

    Limits to 2000 stocks to keep backtest memory/time manageable.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    all_codes = _fetch_all_stock_codes(date)

    MAX_FULL_A = 2000
    if len(all_codes) > MAX_FULL_A:
        logger.warning(f"Full A has {len(all_codes)} stocks, limiting to {MAX_FULL_A}")
        all_codes = all_codes[:MAX_FULL_A]

    return all_codes


def _fetch_all_stock_codes(date: Optional[str] = None) -> List[str]:
    """Fetch all A-share stock codes from baostock."""
    date = date or datetime.now().strftime("%Y-%m-%d")

    # Monthly cache
    cache_dir = _PROJECT_ROOT / "data" / "universe"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"all_a_{date[:7]}.txt"

    if cache_path.exists():
        codes = cache_path.read_text().strip().split("\n")
        if len(codes) > 100:
            return codes

    with _bs_lock:
        _baostock_login()
        try:
            rs = bs.query_all_stock(day=date)
            codes = []
            while rs.error_code == "0" and rs.next():
                row = rs.get_row_data()
                code = row[0]  # code column
                trade_status = row[1] if len(row) > 1 else "1"
                # Filter: only sh/sz, skip indices (000xxx with sh prefix), skip ST-like
                if not (code.startswith("sh.") or code.startswith("sz.")):
                    continue
                # Skip index codes (sh.000xxx)
                if code.startswith("sh.000"):
                    continue
                # Skip Beijing exchange (bj.)
                if code.startswith("bj."):
                    continue
                codes.append(code)

            logger.info(f"All A-share stocks: {len(codes)}")
            cache_path.write_text("\n".join(codes))
            return codes
        finally:
            _baostock_logout()


# --- PLACEHOLDER_FETCHER ---


class MarketDataFetcher:
    """A-share market data fetcher with per-stock Parquet caching."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or str(_PROJECT_ROOT / "data")
        self.stock_cache_dir = os.path.join(self.cache_dir, "stocks")
        os.makedirs(self.stock_cache_dir, exist_ok=True)

    @staticmethod
    def _normalize_stock_code(stock_code: str) -> str:
        """Normalize to baostock format: sh.600519 / sz.000001."""
        stock_code = stock_code.strip()
        if "." in stock_code:
            parts = stock_code.split(".")
            if len(parts) == 2:
                if parts[1].upper() in ("SH", "SZ"):
                    return f"{parts[1].lower()}.{parts[0]}"
                if parts[0].lower() in ("sh", "sz"):
                    return f"{parts[0].lower()}.{parts[1]}"
        if stock_code[:2].lower() in ("sh", "sz"):
            return f"{stock_code[:2].lower()}.{stock_code[2:]}"
        return stock_code

    def _cache_path(self, stock_code: str) -> str:
        safe = self._normalize_stock_code(stock_code).replace(".", "_")
        return os.path.join(self.stock_cache_dir, f"{safe}.parquet")

    def _load_cache(self, stock_code: str) -> Optional[pd.DataFrame]:
        path = self._cache_path(stock_code)
        if os.path.exists(path):
            try:
                df = pd.read_parquet(path)
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                return df
            except Exception as e:
                logger.warning(f"Cache load failed for {stock_code}: {e}")
        return None

    def _save_cache(self, stock_code: str, df: pd.DataFrame):
        if df is None or len(df) == 0:
            return
        df.to_parquet(self._cache_path(stock_code), index=False)

    # --- PLACEHOLDER_FETCH_REMOTE ---

    def _fetch_remote(self, stock_code: str, start_date: str, end_date: str, already_logged_in: bool = False) -> Optional[pd.DataFrame]:
        """Fetch single stock daily data from baostock."""
        code = self._normalize_stock_code(stock_code)
        logged_in = False
        try:
            if not already_logged_in:
                _baostock_login()
                logged_in = True
            rs = bs.query_history_k_data_plus(
                code,
                "date,code,open,high,low,close,volume,amount,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            if not rows:
                return None
            df = pd.DataFrame(rows, columns=rs.fields)
            df = df.rename(columns={"date": "trade_date", "code": "stock_code", "pctChg": "pct_change"})
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            for col in ("open", "high", "low", "close", "volume", "amount", "pct_change"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.sort_values("trade_date")
            if "pct_change" not in df.columns or df["pct_change"].isna().all():
                df["pct_change"] = df["close"].pct_change() * 100
            return df
        except Exception as e:
            logger.error(f"Fetch failed for {stock_code}: {e}")
            return None
        finally:
            if logged_in:
                _baostock_logout()

    # --- PLACEHOLDER_FETCH_STOCKS ---

    def fetch_stocks(
        self,
        stock_codes: List[str],
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch multiple stocks with caching. Missing stocks fetched from baostock."""
        all_data: List[pd.DataFrame] = []
        to_fetch: List[str] = []

        req_start, req_end = pd.Timestamp(start_date), pd.Timestamp(end_date)

        for code in stock_codes:
            cached = self._load_cache(code)
            if cached is not None and len(cached) > 0:
                cache_min = cached["trade_date"].min()
                cache_max = cached["trade_date"].max()
                # Only use cache if it covers the full requested range
                # Allow 5-day tolerance for weekends/holidays at boundaries
                if cache_min <= req_start + pd.Timedelta(days=5) and cache_max >= req_end - pd.Timedelta(days=5):
                    filtered = cached[(cached["trade_date"] >= req_start) & (cached["trade_date"] <= req_end)]
                    if len(filtered) > 0:
                        all_data.append(filtered)
                        continue
            to_fetch.append(code)

        if to_fetch:
            logger.info(f"Fetching {len(to_fetch)} stocks from baostock...")
            with _bs_lock:
                _baostock_login()
                try:
                    for code in to_fetch:
                        df = self._fetch_remote(code, start_date, end_date, already_logged_in=True)
                        if df is not None and len(df) > 0:
                            existing = self._load_cache(code)
                            if existing is not None:
                                df = pd.concat([existing, df]).drop_duplicates("trade_date", keep="last").sort_values("trade_date")
                            self._save_cache(code, df)
                            filtered = df[(df["trade_date"] >= req_start) & (df["trade_date"] <= req_end)]
                            if len(filtered) > 0:
                                all_data.append(filtered)
                finally:
                    _baostock_logout()

        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            logger.info(f"Loaded {len(result):,} records for {result['stock_code'].nunique()} stocks")
            return result
        return None

    def calculate_forward_returns(self, df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
        """Add fwd_ret_{N}d columns."""
        periods = periods or [5]
        df = df.sort_values(["stock_code", "trade_date"])
        for p in periods:
            df[f"fwd_ret_{p}d"] = df.groupby("stock_code")["close"].transform(
                lambda x: x.shift(-p) / x - 1
            )
        return df


# --- PLACEHOLDER_BENCHMARK ---


def fetch_benchmark_returns(
    benchmark: str = "hs300",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> Optional[pd.Series]:
    """Fetch benchmark index daily returns as a Series indexed by date."""
    info = BENCHMARK_CODES.get(benchmark, BENCHMARK_CODES["hs300"])
    code = info["baostock"]
    cache_dir = cache_dir or str(_PROJECT_ROOT / "data" / "benchmark")
    os.makedirs(cache_dir, exist_ok=True)

    cache_path = os.path.join(cache_dir, f"benchmark_{benchmark}.parquet")

    # Try cache first
    if os.path.exists(cache_path):
        try:
            df = pd.read_parquet(cache_path)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.sort_values("trade_date")
            cache_min = df["trade_date"].min()
            cache_max = df["trade_date"].max()
            req_s = pd.Timestamp(start_date) if start_date else cache_min
            req_e = pd.Timestamp(end_date) if end_date else cache_max
            # Only use cache if it covers the full requested range
            if cache_min <= req_s + pd.Timedelta(days=5) and cache_max >= req_e - pd.Timedelta(days=5):
                ret = df.set_index("trade_date")["daily_return"].dropna()
                ret.name = info["name"]
                if start_date:
                    ret = ret[ret.index >= pd.Timestamp(start_date)]
                if end_date:
                    ret = ret[ret.index <= pd.Timestamp(end_date)]
                if len(ret) > 10:
                    return ret
        except Exception:
            pass

    # Fetch from baostock
    start_date = start_date or (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
    end_date = end_date or datetime.now().strftime("%Y-%m-%d")

    with _bs_lock:
        _baostock_login()
        try:
            rs = bs.query_history_k_data_plus(
                code,
                "date,close",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            if not rows:
                return None
            df = pd.DataFrame(rows, columns=rs.fields)
            df["trade_date"] = pd.to_datetime(df["date"])
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df.sort_values("trade_date")
            df["daily_return"] = df["close"].pct_change()
            df[["trade_date", "close", "daily_return"]].to_parquet(cache_path, index=False)
            ret = df.set_index("trade_date")["daily_return"].dropna()
            ret.name = info["name"]
            return ret
        finally:
            _baostock_logout()
