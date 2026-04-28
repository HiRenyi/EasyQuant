"""Tests for factor neutralization."""

import numpy as np
import pandas as pd

from quantgpt.neutralize import cap_neutralize, industry_neutralize, neutralize_factor


def _make_factor_df(n_dates=3, n_stocks=6):
    dates = pd.date_range("2024-01-01", periods=n_dates, freq="D")
    stocks = [f"sh.{600000+i}" for i in range(n_stocks)]
    rows = []
    for d in dates:
        for s in stocks:
            rows.append({"trade_date": d, "stock_code": s})
    df = pd.DataFrame(rows)
    rng = np.random.RandomState(42)
    df["factor_value"] = rng.randn(len(df))
    industries = ["银行", "科技", "消费"]
    df["industry"] = [industries[i % len(industries)] for i in range(len(df))]
    df["market_cap"] = rng.uniform(1e9, 1e11, len(df))
    return df


class TestIndustryNeutralize:
    def test_mean_per_industry_is_zero(self):
        df = _make_factor_df()
        result = industry_neutralize(df)
        df["neutralized"] = result.values
        group_means = df.groupby(["trade_date", "industry"])["neutralized"].mean()
        np.testing.assert_allclose(group_means.values, 0, atol=1e-10)

    def test_preserves_length(self):
        df = _make_factor_df()
        result = industry_neutralize(df)
        assert len(result) == len(df)

    def test_single_industry_zeroes_out_relative_to_mean(self):
        df = _make_factor_df()
        df["industry"] = "银行"
        result = industry_neutralize(df)
        df["neutralized"] = result.values
        for _, g in df.groupby("trade_date"):
            np.testing.assert_allclose(g["neutralized"].mean(), 0, atol=1e-10)


class TestCapNeutralize:
    def test_preserves_length(self):
        df = _make_factor_df()
        result = cap_neutralize(df)
        assert len(result) == len(df)

    def test_residuals_uncorrelated_with_cap(self):
        df = _make_factor_df(n_dates=1, n_stocks=50)
        df["market_cap"] = np.linspace(1e9, 1e11, 50)
        df["factor_value"] = np.log(df["market_cap"]) * 2 + np.random.RandomState(0).randn(50) * 0.1
        result = cap_neutralize(df)
        log_cap = np.log(df["market_cap"].values + 1)
        corr = np.corrcoef(result.values, log_cap)[0, 1]
        assert abs(corr) < 0.1

    def test_too_few_stocks_returns_original(self):
        df = _make_factor_df(n_dates=1, n_stocks=3)
        original = df["factor_value"].copy()
        result = cap_neutralize(df)
        np.testing.assert_array_almost_equal(result.values.flatten(), original.values)


class TestNeutralizeFactorIntegration:
    def test_no_neutralization_returns_original(self):
        market_df = pd.DataFrame({
            "trade_date": pd.date_range("2024-01-01", periods=10),
            "stock_code": [f"sh.{600000+i}" for i in range(10)],
            "close": np.random.RandomState(0).uniform(10, 50, 10),
            "volume": np.random.RandomState(1).uniform(1e6, 1e7, 10),
        })
        factor = pd.Series(np.random.RandomState(2).randn(10))
        result = neutralize_factor(factor, market_df, industry=False, market_cap=False)
        pd.testing.assert_series_equal(result, factor)
