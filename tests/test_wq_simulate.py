"""Tests for WQ BRAIN dollar-neutral portfolio simulation."""

import numpy as np
import pandas as pd
import pytest

from quantgpt.wq_simulate import wq_simulate, _run_is_tests


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
        assert "wq_sharpe" in out
        assert "wq_turnover" in out
        assert "wq_returns" in out
        assert "wq_fitness" in out
        assert "wq_max_weight" in out
        assert "wq_is_tests" in out

    def test_is_tests_structure(self):
        df = _make_work_df()
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        out = wq_simulate(df, rebal_dates)
        tests = out["wq_is_tests"]
        assert "sharpe" in tests
        assert "fitness" in tests
        assert "returns" in tests
        assert "turnover_range" in tests
        assert "weight" in tests
        for v in tests.values():
            assert "value" in v
            assert "label" in v
            assert "pass" in v
            assert isinstance(v["pass"], bool)

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

    def test_too_few_rebalance_dates(self):
        df = _make_work_df(n_days=5)
        out = wq_simulate(df, [df["trade_date"].iloc[0]])
        assert out["wq_sharpe"] == 0.0

    def test_turnover_nonnegative(self):
        df = _make_work_df()
        rebal_dates = sorted(df["trade_date"].unique())[::5]
        out = wq_simulate(df, rebal_dates)
        assert out["wq_turnover"] >= 0

    def test_fitness_formula(self):
        result = _run_is_tests(
            sharpe=2.0, fitness=1.5, returns=0.10,
            turnover=0.15, max_weight=0.05,
        )
        assert result["sharpe"]["pass"] is True
        assert result["fitness"]["pass"] is True
        assert result["returns"]["pass"] is True
        assert result["turnover_range"]["pass"] is True
        assert result["weight"]["pass"] is True

    def test_fitness_formula_fail(self):
        result = _run_is_tests(
            sharpe=0.5, fitness=0.3, returns=0.02,
            turnover=0.80, max_weight=0.15,
        )
        assert result["sharpe"]["pass"] is False
        assert result["fitness"]["pass"] is False
        assert result["returns"]["pass"] is False
        assert result["turnover_range"]["pass"] is False
        assert result["weight"]["pass"] is False
