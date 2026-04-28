"""Tests for WQ BRAIN dollar-neutral portfolio simulation."""

import numpy as np
import pandas as pd

from quantgpt.wq_simulate import _calc_wq_rating, _run_is_tests, _sub_universe_sharpe, wq_simulate


def _make_work_df(n_stocks=20, n_days=60, seed=42):
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2024-01-01", periods=n_days)
    rows = []
    for sc in [f"S{i:03d}" for i in range(n_stocks)]:
        for d in dates:
            rows.append({
                "trade_date": d,
                "stock_code": sc,
                "factor_value": rng.randn(),
                "daily_ret": rng.randn() * 0.02,
            })
    return pd.DataFrame(rows)


class TestWQSimulate:
    def test_basic_output_keys(self):
        df = _make_work_df()
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        out = wq_simulate(df, rebal_dates)
        for key in ["wq_sharpe", "wq_turnover", "wq_returns", "wq_fitness",
                     "wq_max_weight", "wq_rating", "margin_bps", "submittable",
                     "sub_universe", "wq_is_tests"]:
            assert key in out, f"Missing key: {key}"

    def test_is_tests_structure(self):
        df = _make_work_df()
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        out = wq_simulate(df, rebal_dates)
        tests = out["wq_is_tests"]
        for name in ["sharpe", "fitness", "returns", "turnover_range", "weight", "sub_universe"]:
            assert name in tests, f"Missing IS test: {name}"
        for v in tests.values():
            assert "value" in v
            assert "label" in v
            assert "pass" in v
            assert isinstance(v["pass"], bool)

    def test_submittable_flag(self):
        df = _make_work_df()
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        out = wq_simulate(df, rebal_dates)
        assert isinstance(out["submittable"], bool)
        tests = out["wq_is_tests"]
        expected = all(t["pass"] for t in tests.values())
        assert out["submittable"] == expected

    def test_dollar_neutral_weights(self):
        df = _make_work_df(n_stocks=10, n_days=20)
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        out = wq_simulate(df, rebal_dates)
        assert out["wq_max_weight"] > 0
        assert out["wq_max_weight"] <= 0.5

    def test_empty_data(self):
        df = pd.DataFrame(columns=["trade_date", "stock_code", "factor_value", "daily_ret"])
        out = wq_simulate(df, [])
        assert out["wq_sharpe"] == 0.0
        assert out["wq_is_tests"] == {}
        assert out["submittable"] is False

    def test_too_few_rebalance_dates(self):
        df = _make_work_df(n_days=5)
        out = wq_simulate(df, [df["trade_date"].iloc[0]])
        assert out["wq_sharpe"] == 0.0

    def test_turnover_nonnegative(self):
        df = _make_work_df()
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        out = wq_simulate(df, rebal_dates)
        assert out["wq_turnover"] >= 0


class TestWQRating:
    def test_spectacular(self):
        assert _calc_wq_rating(3.0) == "Spectacular"

    def test_excellent(self):
        assert _calc_wq_rating(1.5) == "Excellent"

    def test_good(self):
        assert _calc_wq_rating(1.0) == "Good"

    def test_average(self):
        assert _calc_wq_rating(0.5) == "Average"

    def test_needs_improvement(self):
        assert _calc_wq_rating(0.3) == "Needs Improvement"


class TestSubUniverse:
    def test_basic_structure(self):
        df = _make_work_df(n_stocks=30)
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        result = _sub_universe_sharpe(df, rebal_dates)
        assert "sub_sharpe_a" in result
        assert "sub_sharpe_b" in result
        assert "sub_sharpe_min" in result
        assert "threshold" in result
        assert "pass" in result

    def test_too_few_stocks(self):
        df = _make_work_df(n_stocks=5)
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        result = _sub_universe_sharpe(df, rebal_dates)
        assert result["pass"] is False

    def test_deterministic(self):
        df = _make_work_df(n_stocks=30)
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        r1 = _sub_universe_sharpe(df, rebal_dates, seed=42)
        r2 = _sub_universe_sharpe(df, rebal_dates, seed=42)
        assert r1 == r2


class TestISTests:
    def test_all_pass(self):
        sub = {"sub_sharpe_min": 2.0, "threshold": 1.19, "pass": True}
        result = _run_is_tests(2.0, 1.5, 0.10, 0.15, 0.05, sub)
        assert all(t["pass"] for t in result.values())

    def test_all_fail(self):
        sub = {"sub_sharpe_min": 0.1, "threshold": 1.19, "pass": False}
        result = _run_is_tests(0.5, 0.3, 0.02, 0.80, 0.15, sub)
        assert not any(t["pass"] for t in result.values())

    def test_sub_universe_included(self):
        sub = {"sub_sharpe_min": 0.5, "threshold": 1.19, "pass": False}
        result = _run_is_tests(2.0, 1.5, 0.10, 0.15, 0.05, sub)
        assert "sub_universe" in result
        assert result["sub_universe"]["pass"] is False
