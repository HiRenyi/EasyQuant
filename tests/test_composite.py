"""Tests for composite factor combination engine."""

import numpy as np
import pandas as pd

from quantgpt.composite import combine_factors, compute_factor_correlation


def _make_market_df(n_dates=20, n_stocks=10):
    rng = np.random.RandomState(42)
    dates = pd.bdate_range("2024-01-01", periods=n_dates)
    stocks = [f"sh.{600000+i}" for i in range(n_stocks)]
    rows = []
    for d in dates:
        for s in stocks:
            rows.append({
                "trade_date": d,
                "stock_code": s,
                "open": rng.uniform(10, 100),
                "high": rng.uniform(10, 100),
                "low": rng.uniform(10, 100),
                "close": rng.uniform(10, 100),
                "volume": rng.uniform(1e6, 1e7),
                "amount": rng.uniform(1e7, 1e8),
                "pct_change": rng.uniform(-5, 5),
            })
    return pd.DataFrame(rows)


class TestCombineFactors:
    def test_returns_series_of_correct_length(self):
        df = _make_market_df()
        factors = [
            {"expression": "rank(close)", "weight": 1.0},
            {"expression": "rank(volume)", "weight": 1.0},
        ]
        result = combine_factors(df, factors)
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

    def test_single_factor(self):
        df = _make_market_df()
        factors = [{"expression": "rank(close)", "weight": 1.0}]
        result = combine_factors(df, factors)
        assert not result.isna().all()

    def test_equal_weight_method(self):
        df = _make_market_df()
        factors = [
            {"expression": "rank(close)", "weight": 5.0},
            {"expression": "rank(volume)", "weight": 1.0},
        ]
        result_ew = combine_factors(df, factors, method="equal_weight")
        result_wt = combine_factors(df, factors, method="weighted_rank")
        assert not result_ew.equals(result_wt)

    def test_weighted_zscore_method(self):
        df = _make_market_df()
        factors = [
            {"expression": "rank(close)", "weight": 1.0},
            {"expression": "rank(volume)", "weight": 1.0},
        ]
        result = combine_factors(df, factors, method="weighted_zscore")
        assert len(result) == len(df)

    def test_zero_weights_handled(self):
        df = _make_market_df()
        factors = [
            {"expression": "rank(close)", "weight": 0.0},
            {"expression": "rank(volume)", "weight": 0.0},
        ]
        result = combine_factors(df, factors)
        assert len(result) == len(df)


class TestComputeFactorCorrelation:
    def test_diagonal_is_one(self):
        df = _make_market_df()
        factors = [
            {"expression": "rank(close)", "label": "close_rank"},
            {"expression": "rank(volume)", "label": "vol_rank"},
        ]
        result = compute_factor_correlation(df, factors)
        matrix = result["matrix"]
        assert len(matrix) == 2
        assert abs(matrix[0][0] - 1.0) < 0.01
        assert abs(matrix[1][1] - 1.0) < 0.01

    def test_labels_returned(self):
        df = _make_market_df()
        factors = [
            {"expression": "rank(close)", "label": "F1"},
            {"expression": "rank(volume)", "label": "F2"},
        ]
        result = compute_factor_correlation(df, factors)
        assert result["labels"] == ["F1", "F2"]

    def test_symmetric_matrix(self):
        df = _make_market_df()
        factors = [
            {"expression": "rank(close)"},
            {"expression": "rank(volume)"},
            {"expression": "rank(close * volume)"},
        ]
        result = compute_factor_correlation(df, factors)
        matrix = result["matrix"]
        for i in range(len(matrix)):
            for j in range(len(matrix)):
                assert abs(matrix[i][j] - matrix[j][i]) < 0.01
