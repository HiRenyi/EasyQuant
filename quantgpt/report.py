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
    periods_per_year: int = 252,
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
        periods_per_year=periods_per_year,
    )

    # Patch QuantStats HTML: fix layout for iframe embedding
    _patch_report_css(report_path)

    logger.info(f"Report saved: {report_path}")

    # Extract metrics
    metrics = {
        "total_return": float(qs.stats.comp(returns)),
        "cagr": float(qs.stats.cagr(returns, periods=periods_per_year)),
        "sharpe": float(qs.stats.sharpe(returns, rf=0.03, periods=periods_per_year)),
        "sortino": float(qs.stats.sortino(returns, rf=0.03, periods=periods_per_year)),
        "max_drawdown": float(qs.stats.max_drawdown(returns)),
        "volatility": float(qs.stats.volatility(returns, periods=periods_per_year)),
        "win_rate": float(qs.stats.win_rate(returns)),
        "profit_factor": float(qs.stats.profit_factor(returns)),
    }

    if benchmark_returns is not None:
        metrics["benchmark_total_return"] = float(qs.stats.comp(benchmark_returns))
        metrics["benchmark_cagr"] = float(qs.stats.cagr(benchmark_returns, periods=periods_per_year))

    return {"report_path": report_path, "metrics": metrics}


_CSS_PATCH = """
<style>
/* QuantGPT: fix layout for iframe embedding */
body { margin: 15px !important; }
.container { max-width: 100% !important; display: flex; flex-wrap: wrap; gap: 0; }
.container > h1, .container > h4, .container > hr { width: 100%; flex-shrink: 0; }
#left { float: none !important; width: 62% !important; min-width: 0; margin-right: 0 !important; margin-top: -1.2rem; }
#right { float: none !important; width: 36% !important; min-width: 280px; }
#left svg { width: 100% !important; height: auto !important; }
@media (max-width: 700px) {
    #left, #right { width: 100% !important; }
}
</style>
"""


def _patch_report_css(report_path: str) -> None:
    """Inject responsive CSS into QuantStats HTML report for iframe display."""
    try:
        path = Path(report_path)
        html = path.read_text(encoding="utf-8")
        # Insert our CSS right before </head>
        if "</head>" in html:
            html = html.replace("</head>", _CSS_PATCH + "</head>", 1)
            path.write_text(html, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to patch report CSS: {e}")
