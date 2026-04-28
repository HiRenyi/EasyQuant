"""Walk-forward rolling validation for factor backtesting.

Splits the time series into overlapping train/valid/test windows,
evaluates factor IC/IR in each segment, and produces a composite
robustness score (0-100).
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from .anti_overfit import AntiOverfitDetector

logger = logging.getLogger(__name__)


@dataclass
class WindowResult:
    window_index: int
    train_start: str
    train_end: str
    valid_start: str
    valid_end: str
    test_start: str
    test_end: str
    train_ic: float
    train_ir: float
    valid_ic: float
    valid_ir: float
    test_ic: float
    test_ir: float
    anti_overfit_score: float | None = None
    sharpe: float | None = None


@dataclass
class RollingResult:
    score: float  # 0-100
    windows: list[WindowResult] = field(default_factory=list)
    decay_analysis: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


class RollingValidator:
    """Walk-forward validation with configurable windows.

    Args:
        factor_df: DataFrame with trade_date, stock_code, factor_value, daily_ret.
        holding_period: Holding period in trading days.
        train_years: Training window length in years.
        valid_years: Validation window length in years.
        test_years: Test window length in years.
        step_months: Step size in months between windows.
    """

    def __init__(
        self,
        factor_df: pd.DataFrame,
        holding_period: int = 5,
        train_years: int = 3,
        valid_years: int = 1,
        test_years: int = 1,
        step_months: int = 3,
    ):
        self.df = factor_df.copy()
        self.df["trade_date"] = pd.to_datetime(self.df["trade_date"])
        self.holding_period = holding_period
        self.train_years = train_years
        self.valid_years = valid_years
        self.test_years = test_years
        self.step_months = step_months

    def run(self, run_anti_overfit: bool = False) -> RollingResult:
        """Execute walk-forward validation.

        Args:
            run_anti_overfit: If True, run anti-overfit tests on each window's train set.
        """
        windows = self._generate_windows()
        if not windows:
            return RollingResult(score=0, summary={"error": "数据不足，无法生成验证窗口"})

        results = []
        for i, (train_start, train_end, valid_start, valid_end, test_start, test_end) in enumerate(windows):
            wr = self._evaluate_window(
                i, train_start, train_end, valid_start, valid_end,
                test_start, test_end, run_anti_overfit,
            )
            results.append(wr)

        # Composite score
        score = self._compute_composite_score(results)
        decay = self._analyze_decay(results)

        summary = {
            "n_windows": len(results),
            "mean_test_ic": round(float(np.mean([w.test_ic for w in results])), 4),
            "mean_test_ir": round(float(np.mean([w.test_ir for w in results])), 4),
            "mean_train_ic": round(float(np.mean([w.train_ic for w in results])), 4),
        }

        return RollingResult(score=score, windows=results, decay_analysis=decay, summary=summary)

    def _generate_windows(self) -> list[tuple]:
        """Generate (train_start, train_end, valid_start, valid_end, test_start, test_end) tuples."""
        dates = sorted(self.df["trade_date"].unique())
        if len(dates) < 100:
            return []

        min_date = pd.Timestamp(dates[0])
        max_date = pd.Timestamp(dates[-1])

        windows = []
        current_start = min_date

        while True:
            train_end = current_start + pd.DateOffset(years=self.train_years)
            valid_start = train_end
            valid_end = valid_start + pd.DateOffset(years=self.valid_years)
            test_start = valid_end
            test_end = test_start + pd.DateOffset(years=self.test_years)

            if test_end > max_date:
                break

            windows.append((
                current_start, train_end,
                valid_start, valid_end,
                test_start, test_end,
            ))
            current_start += pd.DateOffset(months=self.step_months)

        return windows

    def _evaluate_window(
        self, idx, train_start, train_end, valid_start, valid_end,
        test_start, test_end, run_anti_overfit_flag,
    ) -> WindowResult:
        """Evaluate IC/IR for a single window."""
        train_df = self.df[(self.df["trade_date"] >= train_start) & (self.df["trade_date"] < train_end)]
        valid_df = self.df[(self.df["trade_date"] >= valid_start) & (self.df["trade_date"] < valid_end)]
        test_df = self.df[(self.df["trade_date"] >= test_start) & (self.df["trade_date"] < test_end)]

        train_ic, train_ir = self._calc_ic_ir(train_df)
        valid_ic, valid_ir = self._calc_ic_ir(valid_df)
        test_ic, test_ir = self._calc_ic_ir(test_df)

        ao_score = None
        if run_anti_overfit_flag and len(train_df) > 100:
            try:
                detector = AntiOverfitDetector(train_df, self.holding_period)
                ao_result = detector.run_all()
                ao_score = ao_result.score
            except Exception as e:
                logger.warning(f"Anti-overfit failed for window {idx}: {e}")

        # Simple Sharpe from test period (using daily_ret mean/std)
        sharpe = None
        if len(test_df) > 0:
            test_ret = test_df.groupby("trade_date")["daily_ret"].mean()
            if len(test_ret) > 0 and test_ret.std() > 0:
                sharpe = round(float(test_ret.mean() / test_ret.std() * np.sqrt(252)), 2)

        return WindowResult(
            window_index=idx,
            train_start=str(train_start.date()),
            train_end=str(train_end.date()),
            valid_start=str(valid_start.date()),
            valid_end=str(valid_end.date()),
            test_start=str(test_start.date()),
            test_end=str(test_end.date()),
            train_ic=round(train_ic, 4),
            train_ir=round(train_ir, 4),
            valid_ic=round(valid_ic, 4),
            valid_ir=round(valid_ir, 4),
            test_ic=round(test_ic, 4),
            test_ir=round(test_ir, 4),
            anti_overfit_score=ao_score,
            sharpe=sharpe,
        )

    def _calc_ic_ir(self, df: pd.DataFrame) -> tuple[float, float]:
        """Calculate mean IC and IR for a data subset."""
        if df.empty:
            return 0.0, 0.0

        sub = df.copy()
        sub = sub.sort_values(["stock_code", "trade_date"])
        sub["fwd_ret"] = (
            sub.groupby("stock_code")["daily_ret"]
            .transform(
                lambda s: s.shift(-1)
                .rolling(self.holding_period, min_periods=self.holding_period)
                .sum()
                .shift(-(self.holding_period - 1))
            )
        )
        valid = sub.dropna(subset=["factor_value", "fwd_ret"])
        if valid.empty:
            return 0.0, 0.0

        def _spearman(g):
            if len(g) < 5 or g["factor_value"].nunique() < 2:
                return np.nan
            corr, _ = sp_stats.spearmanr(g["factor_value"], g["fwd_ret"])
            return corr if not np.isnan(corr) else 0.0

        ic_series = valid.groupby("trade_date").apply(_spearman).dropna()
        if len(ic_series) == 0:
            return 0.0, 0.0

        ic_mean = float(ic_series.mean())
        ic_std = float(ic_series.std())
        ic_ir = float(ic_mean / ic_std) if ic_std > 0 else 0.0
        return ic_mean, ic_ir

    def _compute_composite_score(self, windows: list[WindowResult]) -> float:
        """Compute composite score (0-100) from window results.

        Weights: Test IC 30%, Test IR 25%, IC stability 20%,
                 Anti-overfit 15%, Sharpe 10%.
        """
        if not windows:
            return 0.0

        def _clamp(v, lo, hi):
            return max(lo, min(hi, v))

        # Test IC: mean absolute IC, clamp [0, 0.08] -> [0, 100]
        mean_test_ic = np.mean([abs(w.test_ic) for w in windows])
        test_ic_score = _clamp(mean_test_ic / 0.08, 0, 1) * 100

        # Test IR: mean absolute IR, clamp [0, 1.5] -> [0, 100]
        mean_test_ir = np.mean([abs(w.test_ir) for w in windows])
        test_ir_score = _clamp(mean_test_ir / 1.5, 0, 1) * 100

        # IC stability: std of test ICs across windows, lower is better
        test_ics = [w.test_ic for w in windows]
        if len(test_ics) > 1:
            ic_std = np.std(test_ics)
            # Same sign consistency
            signs = [np.sign(ic) for ic in test_ics if ic != 0]
            consistency = max(sum(1 for s in signs if s > 0), sum(1 for s in signs if s < 0)) / max(len(signs), 1)
            stability_score = consistency * 100 * _clamp(1 - ic_std / 0.05, 0, 1)
        else:
            stability_score = 50.0

        # Anti-overfit: mean of available scores
        ao_scores = [w.anti_overfit_score for w in windows if w.anti_overfit_score is not None]
        ao_score = float(np.mean(ao_scores)) if ao_scores else 50.0  # neutral if not run

        # Sharpe: mean test Sharpe
        sharpes = [w.sharpe for w in windows if w.sharpe is not None]
        if sharpes:
            mean_sharpe = np.mean(sharpes)
            sharpe_score = _clamp((mean_sharpe + 1) / 4, 0, 1) * 100  # [-1, 3] -> [0, 100]
        else:
            sharpe_score = 50.0

        composite = (
            test_ic_score * 0.30
            + test_ir_score * 0.25
            + stability_score * 0.20
            + ao_score * 0.15
            + sharpe_score * 0.10
        )
        return round(_clamp(composite, 0, 100), 1)

    def _analyze_decay(self, windows: list[WindowResult]) -> dict:
        """Analyze IC decay from train to test across windows."""
        decays = []
        for w in windows:
            if abs(w.train_ic) > 0.001:
                decay = (w.train_ic - w.test_ic) / abs(w.train_ic)
                decays.append(decay)

        if not decays:
            return {"status": "insufficient_data"}

        mean_decay = float(np.mean(decays))
        stability = "stable" if abs(mean_decay) < 0.3 else "unstable"

        return {
            "mean_decay": round(mean_decay, 4),
            "status": stability,
            "per_window_decay": [round(d, 4) for d in decays],
        }


def run_rolling_validation(
    factor_df: pd.DataFrame,
    holding_period: int = 5,
    run_anti_overfit: bool = False,
) -> dict:
    """Convenience function: run rolling validation and return serializable dict."""
    validator = RollingValidator(factor_df, holding_period)
    result = validator.run(run_anti_overfit=run_anti_overfit)
    return {
        "score": result.score,
        "summary": result.summary,
        "decay_analysis": result.decay_analysis,
        "windows": [
            {
                "window_index": w.window_index,
                "train_period": f"{w.train_start} ~ {w.train_end}",
                "valid_period": f"{w.valid_start} ~ {w.valid_end}",
                "test_period": f"{w.test_start} ~ {w.test_end}",
                "train_ic": w.train_ic,
                "train_ir": w.train_ir,
                "valid_ic": w.valid_ic,
                "valid_ir": w.valid_ir,
                "test_ic": w.test_ic,
                "test_ir": w.test_ir,
                "anti_overfit_score": w.anti_overfit_score,
                "sharpe": w.sharpe,
            }
            for w in result.windows
        ],
    }
