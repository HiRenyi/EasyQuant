"""Tests for factor attribution module."""


import numpy as np
import pandas as pd

from quantgpt.attribution import _compute_marginal_contributions, _rank_ic


def _make_market_df(n_dates=60, n_stocks=20):
    """Create synthetic market data for testing."""
    rng = np.random.RandomState(42)
    dates = pd.bdate_range("2024-01-01", periods=n_dates)
    stocks = [f"sh.{600000+i}" for i in range(n_stocks)]
    rows = []
    for d in dates:
        for s in stocks:
            rows.append({
                "trade_date": d,
                "stock_code": s,
                "close": rng.uniform(10, 100),
                "volume": rng.uniform(1e6, 1e7),
            })
    return pd.DataFrame(rows)


class TestRankIC:
    def test_perfect_correlation(self):
        factor = pd.Series(range(10), dtype=float)
        returns = pd.Series([x * 0.01 for x in range(10)])
        dates = pd.Series(["2024-01-01"] * 10)
        ic = _rank_ic(factor, returns, dates)
        assert ic > 0.9

    def test_no_correlation(self):
        rng = np.random.RandomState(42)
        n = 100
        factor = pd.Series(rng.randn(n))
        returns = pd.Series(rng.randn(n))
        dates = pd.Series(["2024-01-01"] * 50 + ["2024-01-02"] * 50)
        ic = _rank_ic(factor, returns, dates)
        assert abs(ic) < 0.4

    def test_empty_input(self):
        factor = pd.Series([], dtype=float)
        returns = pd.Series([], dtype=float)
        dates = pd.Series([], dtype=str)
        ic = _rank_ic(factor, returns, dates)
        assert ic == 0.0

    def test_all_nan(self):
        factor = pd.Series([np.nan, np.nan, np.nan])
        returns = pd.Series([np.nan, np.nan, np.nan])
        dates = pd.Series(["2024-01-01"] * 3)
        ic = _rank_ic(factor, returns, dates)
        assert ic == 0.0


class TestMarginalContributions:
    def test_uses_stock_code_column(self):
        """Verify the bug fix: _compute_marginal_contributions uses 'stock_code' column."""
        market_df = _make_market_df(n_dates=30, n_stocks=10)
        assert "stock_code" in market_df.columns
        assert "code" not in market_df.columns

        sub_factors = [
            {"expression": "rank(close)", "label": "F1"},
            {"expression": "rank(volume)", "label": "F2"},
        ]
        result = _compute_marginal_contributions(market_df, sub_factors, n_groups=5, holding_period=5)
        assert isinstance(result, list)

    def test_returns_empty_for_single_factor(self):
        market_df = _make_market_df()
        sub_factors = [{"expression": "rank(close)", "label": "F1"}]
        result = _compute_marginal_contributions(market_df, sub_factors, n_groups=5, holding_period=5)
        assert result == []

    def test_contribution_structure(self):
        market_df = _make_market_df(n_dates=30, n_stocks=10)
        sub_factors = [
            {"expression": "rank(close)", "label": "F1"},
            {"expression": "rank(volume)", "label": "F2"},
        ]
        result = _compute_marginal_contributions(market_df, sub_factors, n_groups=5, holding_period=5)
        assert len(result) == 2
        for item in result:
            assert "label" in item
            assert "marginal_ic" in item

    def test_sorted_by_absolute_marginal_ic(self):
        market_df = _make_market_df(n_dates=30, n_stocks=10)
        sub_factors = [
            {"expression": "rank(close)", "label": "F1"},
            {"expression": "rank(volume)", "label": "F2"},
            {"expression": "rank(close * volume)", "label": "F3"},
        ]
        result = _compute_marginal_contributions(market_df, sub_factors, n_groups=5, holding_period=5)
        marginal_ics = [abs(r["marginal_ic"]) for r in result]
        assert marginal_ics == sorted(marginal_ics, reverse=True)
