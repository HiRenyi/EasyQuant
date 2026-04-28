"""Anti-overfit detection for factor backtesting.

Provides 4 statistical tests to assess whether a factor's performance
is robust or likely overfitted:
1. IC Stability — yearly Spearman IC consistency
2. Sub-sample Stress — IC across market regimes
3. Placebo Test — random permutation + time-shift
4. Half-life Estimation — IC decay across forward periods
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from scipy.optimize import curve_fit

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    name: str
    passed: bool
    details: dict


@dataclass
class AntiOverfitResult:
    score: float  # 0-100
    recommendation: str  # "推荐" / "谨慎" / "需改进" / "不推荐"
    tests: list[TestResult] = field(default_factory=list)
    passed_count: int = 0
    total_count: int = 4


class AntiOverfitDetector:
    """Detect potential overfitting in factor backtests.

    Args:
        factor_df: DataFrame with columns trade_date, stock_code, factor_value, daily_ret.
        holding_period: Holding period in trading days.
    """

    def __init__(self, factor_df: pd.DataFrame, holding_period: int = 5):
        self.df = factor_df.copy()
        self.df["trade_date"] = pd.to_datetime(self.df["trade_date"])
        self.holding_period = holding_period
        self._prepare_forward_returns()

    def _prepare_forward_returns(self):
        """Compute forward N-day return for IC calculations."""
        self.df = self.df.sort_values(["stock_code", "trade_date"])
        self.df["fwd_ret"] = (
            self.df.groupby("stock_code")["daily_ret"]
            .transform(
                lambda s: s.shift(-1)
                .rolling(self.holding_period, min_periods=self.holding_period)
                .sum()
                .shift(-(self.holding_period - 1))
            )
        )

    def _calc_daily_ic(self, df: pd.DataFrame | None = None) -> pd.Series:
        """Calculate daily Spearman IC between factor_value and fwd_ret."""
        data = df if df is not None else self.df
        valid = data.dropna(subset=["factor_value", "fwd_ret"])
        if valid.empty:
            return pd.Series(dtype=float)

        def _spearman(g):
            if len(g) < 5 or g["factor_value"].nunique() < 2:
                return np.nan
            corr, _ = sp_stats.spearmanr(g["factor_value"], g["fwd_ret"])
            return corr if not np.isnan(corr) else 0.0

        return valid.groupby("trade_date").apply(_spearman).dropna()

    def run_all(self) -> AntiOverfitResult:
        """Run all 4 anti-overfit tests and return composite result."""
        tests = [
            self.test_ic_stability(),
            self.test_subsample_stress(),
            self.test_placebo(),
            self.test_half_life(),
        ]
        passed = sum(1 for t in tests if t.passed)
        score = passed / 4 * 100

        if score >= 80:
            rec = "推荐"
        elif score >= 60:
            rec = "谨慎"
        elif score >= 40:
            rec = "需改进"
        else:
            rec = "不推荐"

        return AntiOverfitResult(
            score=score,
            recommendation=rec,
            tests=tests,
            passed_count=passed,
            total_count=4,
        )

    # ---- Test 1: IC Stability ----

    def test_ic_stability(self) -> TestResult:
        """Check IC consistency across years.

        Pass conditions:
        - Positive IC rate >= 55%
        - Mean IC >= 0.02
        - No yearly IC reversal (all years same sign as overall)
        """
        ic_series = self._calc_daily_ic()
        if len(ic_series) < 20:
            return TestResult("IC稳定性", False, {"error": "IC数据不足"})

        ic_mean = float(ic_series.mean())
        positive_rate = float((ic_series > 0).sum() / len(ic_series))

        # Yearly IC
        yearly_ic = ic_series.groupby(ic_series.index.year).mean()
        overall_sign = np.sign(ic_mean)
        yearly_signs = np.sign(yearly_ic.values)
        has_reversal = bool(np.any(yearly_signs != overall_sign)) if overall_sign != 0 else True

        passed = (positive_rate >= 0.55) and (abs(ic_mean) >= 0.02) and (not has_reversal)

        return TestResult("IC稳定性", passed, {
            "ic_mean": round(ic_mean, 4),
            "positive_rate": round(positive_rate, 4),
            "yearly_ic": {str(y): round(float(v), 4) for y, v in yearly_ic.items()},
            "has_reversal": has_reversal,
        })

    # ---- Test 2: Sub-sample Stress ----

    def test_subsample_stress(self) -> TestResult:
        """Check IC consistency across market regimes.

        Splits data by:
        - Market regime: bull (>0 cumret) / bear (<0 cumret) / sideways
        - Volatility: high / low (median split)

        Pass: >= 60% of sub-samples have IC same sign as overall.
        """
        ic_series = self._calc_daily_ic()
        if len(ic_series) < 40:
            return TestResult("子样本压力", False, {"error": "数据不足"})

        overall_sign = np.sign(ic_series.mean())
        if overall_sign == 0:
            return TestResult("子样本压力", False, {"error": "整体IC为零"})

        # Market daily returns (equal-weighted market return)
        market_ret = self.df.groupby("trade_date")["daily_ret"].mean()
        market_ret = market_ret.reindex(ic_series.index).fillna(0)

        # Rolling 60-day cumulative return to classify regime
        cum_ret_60 = market_ret.rolling(60, min_periods=30).sum()
        volatility_60 = market_ret.rolling(60, min_periods=30).std()

        sub_ics = {}
        # Bull / Bear / Sideways
        bull_mask = cum_ret_60 > 0.05
        bear_mask = cum_ret_60 < -0.05
        sideways_mask = ~bull_mask & ~bear_mask

        for name, mask in [("bull", bull_mask), ("bear", bear_mask), ("sideways", sideways_mask)]:
            aligned_mask = mask.reindex(ic_series.index).fillna(False)
            sub = ic_series[aligned_mask]
            if len(sub) >= 10:
                sub_ics[name] = float(sub.mean())

        # High / Low volatility
        vol_median = volatility_60.median()
        high_vol = volatility_60 > vol_median
        low_vol = ~high_vol
        for name, mask in [("high_vol", high_vol), ("low_vol", low_vol)]:
            aligned_mask = mask.reindex(ic_series.index).fillna(False)
            sub = ic_series[aligned_mask]
            if len(sub) >= 10:
                sub_ics[name] = float(sub.mean())

        if len(sub_ics) == 0:
            return TestResult("子样本压力", False, {"error": "子样本划分失败"})

        same_sign_count = sum(1 for v in sub_ics.values() if np.sign(v) == overall_sign)
        consistency = same_sign_count / len(sub_ics)
        passed = consistency >= 0.6

        return TestResult("子样本压力", passed, {
            "overall_ic_sign": int(overall_sign),
            "sub_sample_ics": {k: round(v, 4) for k, v in sub_ics.items()},
            "consistency": round(consistency, 4),
        })

    # ---- Test 3: Placebo Test ----

    def test_placebo(self, n_permutations: int = 20) -> TestResult:
        """Random permutation + time-shift placebo test.

        Pass conditions:
        - Real IC > 95th percentile of permuted ICs
        - Time-shifted IC (5/10/20 day) shows decay
        """
        ic_series = self._calc_daily_ic()
        if len(ic_series) < 20:
            return TestResult("安慰剂检验", False, {"error": "IC数据不足"})

        real_ic = float(ic_series.mean())

        # Permutation test: shuffle factor_value across stocks within each date
        # Sample dates to limit computation (use every 5th date)
        perm_ics = []
        rng = np.random.RandomState(42)
        valid = self.df.dropna(subset=["factor_value", "fwd_ret"])
        sampled_dates = sorted(valid["trade_date"].unique())[::5]
        valid_sampled = valid[valid["trade_date"].isin(sampled_dates)]
        for _ in range(n_permutations):
            shuffled = valid_sampled.copy()
            shuffled["factor_value"] = shuffled.groupby("trade_date")["factor_value"].transform(
                lambda s: s.sample(frac=1, random_state=rng).values
            )
            perm_ic = self._calc_daily_ic(shuffled)
            if len(perm_ic) > 0:
                perm_ics.append(float(perm_ic.mean()))

        if len(perm_ics) < 10:
            return TestResult("安慰剂检验", False, {"error": "置换检验数据不足"})

        perm_95 = float(np.percentile(perm_ics, 95))
        perm_pass = abs(real_ic) > abs(perm_95)

        # Time-shift test: shift factor values by 5/10/20 days
        shift_ics = {}
        for shift in [5, 10, 20]:
            shifted = self.df.copy()
            shifted["factor_value"] = shifted.groupby("stock_code")["factor_value"].shift(shift)
            shift_ic = self._calc_daily_ic(shifted)
            if len(shift_ic) > 0:
                shift_ics[shift] = float(shift_ic.mean())

        # Check decay: shifted ICs should have lower absolute value
        decay_ok = True
        if shift_ics:
            for shift_val in shift_ics.values():
                if abs(shift_val) >= abs(real_ic):
                    decay_ok = False
                    break

        passed = perm_pass and decay_ok

        return TestResult("安慰剂检验", passed, {
            "real_ic": round(real_ic, 4),
            "perm_95th": round(perm_95, 4),
            "perm_pass": perm_pass,
            "shift_ics": {str(k): round(v, 4) for k, v in shift_ics.items()},
            "decay_ok": decay_ok,
        })

    # ---- Test 4: Half-life Estimation ----

    def test_half_life(self) -> TestResult:
        """Estimate IC half-life by fitting exponential decay across forward periods.

        Computes IC for multiple forward periods (1, 2, 5, 10, 20, 40 days),
        fits exponential decay, and checks half_life > 5 days.
        """
        periods = [1, 2, 5, 10, 20, 40]
        period_ics = {}

        valid = self.df.dropna(subset=["factor_value"]).copy()
        valid = valid.sort_values(["stock_code", "trade_date"])
        # Sample every 3rd date to speed up multi-period IC calculation
        sampled_dates = sorted(valid["trade_date"].unique())[::3]
        valid = valid[valid["trade_date"].isin(sampled_dates)]

        for p in periods:
            valid[f"fwd_ret_{p}"] = (
                valid.groupby("stock_code")["daily_ret"]
                .transform(
                    lambda s: s.shift(-1)
                    .rolling(p, min_periods=p)
                    .sum()
                    .shift(-(p - 1))
                )
            )
            sub = valid.dropna(subset=["factor_value", f"fwd_ret_{p}"])
            if sub.empty:
                continue

            def _spearman_p(g, col=f"fwd_ret_{p}"):
                if len(g) < 5 or g["factor_value"].nunique() < 2:
                    return np.nan
                corr, _ = sp_stats.spearmanr(g["factor_value"], g[col])
                return corr if not np.isnan(corr) else 0.0

            ic_s = sub.groupby("trade_date").apply(_spearman_p).dropna()
            if len(ic_s) > 0:
                period_ics[p] = abs(float(ic_s.mean()))

        if len(period_ics) < 3:
            return TestResult("半衰期估计", False, {"error": "前瞻期IC数据不足"})

        # Fit exponential decay: IC(t) = a * exp(-b * t)
        x = np.array(list(period_ics.keys()), dtype=float)
        y = np.array(list(period_ics.values()), dtype=float)

        try:
            def exp_decay(t, a, b):
                return a * np.exp(-b * t)

            popt, _ = curve_fit(exp_decay, x, y, p0=[y[0], 0.05], maxfev=5000)
            a, b = popt
            half_life = float(np.log(2) / b) if b > 0 else 999.0
        except Exception:
            # Fallback: simple ratio estimation
            if len(period_ics) >= 2:
                sorted_p = sorted(period_ics.items())
                ic_first = sorted_p[0][1]
                ic_last = sorted_p[-1][1]
                t_span = sorted_p[-1][0] - sorted_p[0][0]
                if ic_first > 0 and ic_last > 0 and ic_last < ic_first:
                    b_est = np.log(ic_first / ic_last) / t_span
                    half_life = float(np.log(2) / b_est) if b_est > 0 else 999.0
                else:
                    half_life = 999.0
            else:
                half_life = 0.0

        passed = half_life > 5.0

        return TestResult("半衰期估计", passed, {
            "half_life_days": round(half_life, 1),
            "period_ics": {str(k): round(v, 4) for k, v in period_ics.items()},
        })


def run_anti_overfit(factor_df: pd.DataFrame, holding_period: int = 5) -> dict:
    """Convenience function: run all anti-overfit tests and return serializable dict."""
    detector = AntiOverfitDetector(factor_df, holding_period)
    result = detector.run_all()
    return {
        "score": result.score,
        "recommendation": result.recommendation,
        "passed_count": result.passed_count,
        "total_count": result.total_count,
        "tests": [
            {
                "name": t.name,
                "passed": t.passed,
                "details": t.details,
            }
            for t in result.tests
        ],
    }
