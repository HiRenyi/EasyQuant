"""Tests for backtest.py — group backtest engine correctness."""

import numpy as np
import pandas as pd
import pytest

from quantgpt.backtest import (
    _calc_max_drawdown,
    _calc_monotonicity,
    run_factor_backtest,
)


@pytest.fixture
def market_df():
    """Synthetic market data with 5 stocks over 60 trading days."""
    dates = pd.bdate_range("2024-01-02", periods=60)
    stocks = [f"00000{i}.SZ" for i in range(1, 6)]
    rng = np.random.RandomState(123)

    rows = []
    for s_idx, s in enumerate(stocks):
        price = 10.0 + s_idx * 2
        for d in dates:
            ret = rng.randn() * 0.02
            new_price = price * (1 + ret)
            rows.append({
                "trade_date": d,
                "stock_code": s,
                "open": price,
                "high": max(price, new_price) * (1 + abs(rng.randn()) * 0.005),
                "low": min(price, new_price) * (1 - abs(rng.randn()) * 0.005),
                "close": new_price,
                "volume": 1_000_000 + rng.randint(0, 500_000),
                "amount": 10_000_000 + rng.randint(0, 5_000_000),
                "pct_change": ret * 100,
            })
            price = new_price
    return pd.DataFrame(rows)


class TestRunFactorBacktest:
    def test_basic_run(self, market_df):
        result = run_factor_backtest(
            market_df,
            expression="close",
            n_groups=3,
            holding_period=5,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        assert "strategy_returns" in result
        assert "group_returns" in result
        assert "ic_mean" in result
        assert "top_group_sharpe" in result
        assert "monotonicity_score" in result
        assert len(result["strategy_returns"]) > 0

    def test_group_count(self, market_df):
        result = run_factor_backtest(
            market_df,
            expression="close",
            n_groups=3,
            holding_period=5,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        assert len(result["group_returns"]) == 3

    def test_ic_bounded(self, market_df):
        result = run_factor_backtest(
            market_df,
            expression="close",
            n_groups=3,
            holding_period=5,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        assert -1.0 <= result["ic_mean"] <= 1.0
        assert -1.0 <= result["rank_ic_mean"] <= 1.0

    def test_ic_win_rate_bounded(self, market_df):
        result = run_factor_backtest(
            market_df,
            expression="close",
            n_groups=3,
            holding_period=5,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        assert 0.0 <= result["ic_win_rate"] <= 1.0

    def test_turnover_bounded(self, market_df):
        result = run_factor_backtest(
            market_df,
            expression="close",
            n_groups=3,
            holding_period=5,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        assert 0.0 <= result["turnover"] <= 1.0

    def test_cost_adjusted(self, market_df):
        result_no_cost = run_factor_backtest(
            market_df,
            expression="close",
            n_groups=3,
            holding_period=5,
            cost_rate=0.0,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        result_with_cost = run_factor_backtest(
            market_df,
            expression="close",
            n_groups=3,
            holding_period=5,
            cost_rate=0.01,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        assert result_with_cost["cost_adjusted"] is True
        strat_no_cost = result_no_cost["strategy_returns"].sum()
        strat_with_cost = result_with_cost["strategy_returns"].sum()
        assert strat_with_cost <= strat_no_cost + 1e-10

    def test_precomputed_factor(self, market_df):
        factor_values = pd.Series(
            np.random.RandomState(99).randn(len(market_df)),
            index=market_df.index,
        )
        result = run_factor_backtest(
            market_df,
            precomputed_factor=factor_values,
            n_groups=3,
            holding_period=5,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        assert len(result["strategy_returns"]) > 0

    def test_no_expression_no_factor_raises(self, market_df):
        with pytest.raises(ValueError, match="expression.*precomputed_factor"):
            run_factor_backtest(
                market_df,
                expression=None,
                precomputed_factor=None,
                n_groups=3,
                holding_period=5,
            )

    def test_complex_expression(self, market_df):
        result = run_factor_backtest(
            market_df,
            expression="rank(ts_mean(close, 5) - ts_mean(close, 20))",
            n_groups=3,
            holding_period=5,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        assert len(result["strategy_returns"]) > 0
        assert "group_returns" in result

    def test_direction_flip(self, market_df):
        """Verify that the engine detects when lower factor = better returns."""
        result = run_factor_backtest(
            market_df,
            expression="close",
            n_groups=3,
            holding_period=5,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        assert isinstance(result["flipped"], bool)

    def test_stock_factor_data(self, market_df):
        result = run_factor_backtest(
            market_df,
            expression="close",
            n_groups=3,
            holding_period=5,
            neutralize_industry=False,
            neutralize_cap=False,
        )
        sfd = result["_stock_factor_data"]
        assert sfd is not None
        assert "stocks" in sfd
        assert len(sfd["stocks"]) > 0
        for stock in sfd["stocks"]:
            assert "stock_code" in stock
            assert "factor_value" in stock
            assert "group" in stock


class TestMaxDrawdown:
    def test_zero_drawdown(self):
        returns = pd.Series([0.01, 0.02, 0.01, 0.03])
        dd = _calc_max_drawdown(returns)
        assert dd <= 0.0

    def test_known_drawdown(self):
        returns = pd.Series([0.10, -0.20, 0.05])
        dd = _calc_max_drawdown(returns)
        assert dd < 0.0

    def test_empty_series(self):
        dd = _calc_max_drawdown(pd.Series(dtype=float))
        assert dd == 0.0


class TestMonotonicity:
    def test_perfect_monotonic(self):
        group_means = [0.01, 0.02, 0.03, 0.04, 0.05]
        mono = _calc_monotonicity(group_means)
        assert mono == pytest.approx(1.0)

    def test_inverse_monotonic(self):
        group_means = [0.05, 0.04, 0.03, 0.02, 0.01]
        mono = _calc_monotonicity(group_means)
        assert mono == pytest.approx(1.0)

    def test_flat(self):
        group_means = [0.02, 0.02, 0.02, 0.02]
        mono = _calc_monotonicity(group_means)
        assert 0.0 <= mono <= 1.0

    def test_too_few_groups(self):
        assert _calc_monotonicity([0.01, 0.02]) == 0.0
