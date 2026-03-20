"""QuantStats HTML report generation + metrics extraction."""

import logging
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, must be before any pyplot import
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def generate_report(
    ls_returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    title: str = "Factor Long-Short Backtest",
    output_dir: Optional[str] = None,
) -> dict:
    """Generate QuantStats HTML report and extract key metrics.

    Args:
        ls_returns: Daily long-short return series indexed by date.
        benchmark_returns: Optional benchmark daily returns for comparison.
        title: Report title.
        output_dir: Directory for HTML output. Defaults to <project>/reports.

    Returns:
        Dict with report_path and metrics.
    """
    import quantstats as qs

    output_dir = Path(output_dir) if output_dir else (_PROJECT_ROOT / "reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    returns = ls_returns.sort_index().copy()
    returns.index = pd.to_datetime(returns.index).normalize()
    returns.name = "Strategy"

    if benchmark_returns is not None:
        benchmark_returns = benchmark_returns.copy()
        benchmark_returns.index = pd.to_datetime(benchmark_returns.index).normalize()
        benchmark_returns = benchmark_returns.sort_index()
        # Align benchmark to returns dates
        bm_aligned = benchmark_returns.reindex(returns.index, method="ffill")
        valid = ~bm_aligned.isna()
        if valid.sum() < 2:
            logger.warning("Insufficient benchmark overlap, generating report without benchmark")
            benchmark_returns = None
        else:
            returns = returns[valid]
            benchmark_returns = bm_aligned[valid]

    # Generate HTML
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    report_path = str(output_dir / f"backtest_report_{timestamp}.html")

    qs.reports.html(
        returns,
        benchmark=benchmark_returns,
        output=report_path,
        title=title,
        rf=0.03,
        match_dates=False,
    )
    logger.info(f"Report saved: {report_path}")

    # Extract metrics
    metrics = {
        "total_return": float(qs.stats.comp(returns)),
        "cagr": float(qs.stats.cagr(returns)),
        "sharpe": float(qs.stats.sharpe(returns, rf=0.03)),
        "sortino": float(qs.stats.sortino(returns, rf=0.03)),
        "max_drawdown": float(qs.stats.max_drawdown(returns)),
        "volatility": float(qs.stats.volatility(returns)),
        "win_rate": float(qs.stats.win_rate(returns)),
        "profit_factor": float(qs.stats.profit_factor(returns)),
    }

    return {"report_path": report_path, "metrics": metrics}
