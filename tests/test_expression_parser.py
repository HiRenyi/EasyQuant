"""Tests for expression_parser.py — operator correctness and edge cases."""

import numpy as np
import pandas as pd
import pytest

from quantgpt.expression_parser import parse_expression


@pytest.fixture
def sample_df():
    """Multi-stock, multi-date DataFrame for cross-sectional and time-series tests."""
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    stocks = ["000001.SZ", "000002.SZ", "600000.SH"]
    rows = []
    rng = np.random.RandomState(42)
    for d in dates:
        for s in stocks:
            rows.append({
                "trade_date": d,
                "stock_code": s,
                "open": 10 + rng.randn(),
                "high": 11 + abs(rng.randn()),
                "low": 9 + abs(rng.randn()),
                "close": 10 + rng.randn(),
                "volume": 1_000_000 + rng.randint(0, 500_000),
                "amount": 10_000_000 + rng.randint(0, 5_000_000),
                "pct_change": rng.randn() * 0.02,
            })
    return pd.DataFrame(rows)


class TestColumnReference:
    def test_close_column(self, sample_df):
        fn = parse_expression("close")
        result = fn(sample_df)
        pd.testing.assert_series_equal(result, sample_df["close"], check_names=False)

    def test_unknown_column_raises(self):
        with pytest.raises(ValueError, match="Unknown column"):
            parse_expression("nonexistent_col")


class TestNumericLiteral:
    def test_integer(self, sample_df):
        fn = parse_expression("42")
        result = fn(sample_df)
        assert (result == 42.0).all()

    def test_float(self, sample_df):
        fn = parse_expression("3.14")
        result = fn(sample_df)
        assert np.allclose(result, 3.14)


class TestArithmetic:
    def test_addition(self, sample_df):
        fn = parse_expression("close + open")
        result = fn(sample_df)
        expected = sample_df["close"] + sample_df["open"]
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_subtraction(self, sample_df):
        fn = parse_expression("close - open")
        result = fn(sample_df)
        expected = sample_df["close"] - sample_df["open"]
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_multiplication(self, sample_df):
        fn = parse_expression("close * volume")
        result = fn(sample_df)
        expected = sample_df["close"] * sample_df["volume"]
        pd.testing.assert_series_equal(result, expected, check_names=False)

    def test_division_zero_produces_nan(self, sample_df):
        df = sample_df.copy()
        df.loc[0, "volume"] = 0
        fn = parse_expression("close / volume")
        result = fn(df)
        assert np.isnan(result.iloc[0])

    def test_unary_negation(self, sample_df):
        fn = parse_expression("-close")
        result = fn(sample_df)
        expected = -sample_df["close"]
        pd.testing.assert_series_equal(result, expected, check_names=False)


class TestUnaryOps:
    def test_log_clamps_negative(self, sample_df):
        fn = parse_expression("log(close)")
        result = fn(sample_df)
        assert not result.isna().any()

    def test_abs(self, sample_df):
        fn = parse_expression("abs(close - 10)")
        result = fn(sample_df)
        assert (result >= 0).all()

    def test_sign(self, sample_df):
        fn = parse_expression("sign(close - 10)")
        result = fn(sample_df)
        assert set(result.unique()).issubset({-1.0, 0.0, 1.0})

    def test_sqrt_clamps_negative(self, sample_df):
        fn = parse_expression("sqrt(close - 100)")
        result = fn(sample_df)
        assert (result >= 0).all() or result.isna().all()

    def test_sigmoid_range(self, sample_df):
        fn = parse_expression("sigmoid(close)")
        result = fn(sample_df)
        assert (result >= 0).all() and (result <= 1).all()


class TestCrossSectionalOps:
    def test_rank_per_date(self, sample_df):
        fn = parse_expression("rank(close)")
        result = fn(sample_df)
        assert result.min() >= 0.0
        assert result.max() <= 1.0
        for _, group in sample_df.groupby("trade_date"):
            date_ranks = result.loc[group.index]
            assert date_ranks.max() <= 1.0

    def test_zscore_per_date(self, sample_df):
        fn = parse_expression("zscore(close)")
        result = fn(sample_df)
        for _, group in sample_df.groupby("trade_date"):
            z = result.loc[group.index]
            assert abs(z.mean()) < 1e-6


class TestTimeSeriesOps:
    def test_ts_mean(self, sample_df):
        fn = parse_expression("ts_mean(close, 5)")
        result = fn(sample_df)
        assert len(result) == len(sample_df)
        assert not result.isna().all()

    def test_ts_delta(self, sample_df):
        fn = parse_expression("ts_delta(close, 1)")
        result = fn(sample_df)
        assert len(result) == len(sample_df)

    def test_ts_std(self, sample_df):
        fn = parse_expression("ts_std(close, 10)")
        result = fn(sample_df)
        valid = result.dropna()
        assert (valid >= 0).all()

    def test_decay_linear(self, sample_df):
        fn = parse_expression("decay_linear(close, 5)")
        result = fn(sample_df)
        assert len(result) == len(sample_df)

    def test_ts_corr_dual_column(self, sample_df):
        fn = parse_expression("ts_corr(close, volume, 10)")
        result = fn(sample_df)
        valid = result.dropna()
        assert (valid >= -1.0001).all() and (valid <= 1.0001).all()


class TestTechnicalIndicators:
    def test_rsi_range(self, sample_df):
        fn = parse_expression("rsi(close, 14)")
        result = fn(sample_df)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_ema(self, sample_df):
        fn = parse_expression("ema(close, 10)")
        result = fn(sample_df)
        assert not result.isna().all()

    def test_boll_upper_gt_lower(self, sample_df):
        upper = parse_expression("boll_upper(close, 20)")(sample_df)
        lower = parse_expression("boll_lower(close, 20)")(sample_df)
        valid_mask = upper.notna() & lower.notna()
        assert (upper[valid_mask] >= lower[valid_mask]).all()


class TestConditionalOps:
    def test_where(self, sample_df):
        fn = parse_expression("where(close > 10, close, 0)")
        result = fn(sample_df)
        for i, row in sample_df.iterrows():
            if row["close"] > 10:
                assert result.iloc[sample_df.index.get_loc(i)] == pytest.approx(row["close"])

    def test_clip(self, sample_df):
        fn = parse_expression("clip(close, 9, 11)")
        result = fn(sample_df)
        assert result.min() >= 9.0
        assert result.max() <= 11.0


class TestSpecialVariables:
    def test_returns(self, sample_df):
        fn = parse_expression("returns")
        result = fn(sample_df)
        assert len(result) == len(sample_df)

    def test_vwap(self, sample_df):
        fn = parse_expression("vwap")
        result = fn(sample_df)
        assert not result.isna().all()


class TestOperatorAliases:
    def test_delta_alias(self, sample_df):
        fn1 = parse_expression("ts_delta(close, 5)")
        fn2 = parse_expression("delta(close, 5)")
        pd.testing.assert_series_equal(fn1(sample_df), fn2(sample_df))

    def test_delay_alias(self, sample_df):
        fn1 = parse_expression("ts_shift(close, 1)")
        fn2 = parse_expression("delay(close, 1)")
        pd.testing.assert_series_equal(fn1(sample_df), fn2(sample_df))


class TestCompositeExpressions:
    def test_nested_functions(self, sample_df):
        fn = parse_expression("rank(ts_mean(close, 5))")
        result = fn(sample_df)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_arithmetic_with_functions(self, sample_df):
        fn = parse_expression("ts_mean(close, 5) - ts_mean(close, 20)")
        result = fn(sample_df)
        assert len(result) == len(sample_df)

    def test_complex_expression(self, sample_df):
        fn = parse_expression("rank(ts_delta(close, 5) / ts_std(close, 20))")
        result = fn(sample_df)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 1).all()


class TestValidation:
    def test_max_depth_exceeded(self):
        deep = "abs(" * 110 + "close" + ")" * 110
        with pytest.raises(ValueError, match="nesting too deep"):
            parse_expression(deep)

    def test_max_length_exceeded(self):
        long_expr = "close + " * 200 + "close"
        with pytest.raises(ValueError, match="too long"):
            parse_expression(long_expr)

    def test_invalid_window_zero(self):
        with pytest.raises(ValueError):
            parse_expression("ts_mean(close, 0)")

    def test_invalid_window_too_large(self):
        with pytest.raises(ValueError):
            parse_expression("ts_mean(close, 9999)")

    def test_unknown_function(self):
        with pytest.raises(ValueError, match="Unknown function"):
            parse_expression("bogus_func(close, 5)")
