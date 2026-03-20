import type { BacktestResult } from "../types/backtest";
import MetricCard from "./MetricCard";
import GroupReturnsTable from "./GroupReturnsTable";
import ReportViewer from "./ReportViewer";

interface Props {
  result: BacktestResult;
}

function pct(n: number): string {
  return (n * 100).toFixed(2) + "%";
}

function num(n: number): string {
  return n.toFixed(4);
}

export default function ResultsDashboard({ result }: Props) {
  const { metrics, backtest_summary, report_url, params } = result;

  return (
    <div className="space-y-5">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-1 h-4 rounded-full bg-[var(--accent-green)]" />
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-[0.15em]">
            回测结果
          </h3>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-[var(--text-muted)] font-mono">
            {params.universe.toUpperCase()}
          </span>
          <span className="w-px h-3 bg-[var(--border-subtle)]" />
          <span className="text-[10px] text-[var(--text-muted)] font-mono">
            {params.start_date} → {params.end_date}
          </span>
          <span className="w-px h-3 bg-[var(--border-subtle)]" />
          <span className="text-[10px] text-[var(--text-muted)] font-mono">
            {params.stock_count} stocks
          </span>
        </div>
      </div>

      {/* Primary metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard label="总收益" value={pct(metrics.total_return)} color={metrics.total_return >= 0 ? "green" : "red"} />
        <MetricCard label="年化收益" value={pct(metrics.cagr)} color={metrics.cagr >= 0 ? "green" : "red"} />
        <MetricCard label="Sharpe" value={num(metrics.sharpe)} color={metrics.sharpe >= 1 ? "green" : "default"} />
        <MetricCard label="Sortino" value={num(metrics.sortino)} />
        <MetricCard label="最大回撤" value={pct(metrics.max_drawdown)} color="red" />
        <MetricCard label="波动率" value={pct(metrics.volatility)} />
        <MetricCard label="胜率" value={pct(metrics.win_rate)} />
        <MetricCard label="盈亏比" value={num(metrics.profit_factor)} />
      </div>

      {/* Summary metrics */}
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="多空 Sharpe" value={num(backtest_summary.long_short_sharpe)} color={backtest_summary.long_short_sharpe >= 1 ? "green" : "default"} />
        <MetricCard label="单调性" value={num(backtest_summary.monotonicity_score)} />
        <MetricCard label="多空价差" value={pct(backtest_summary.spread)} color={backtest_summary.spread >= 0 ? "green" : "red"} />
      </div>

      <GroupReturnsTable groupReturns={backtest_summary.group_returns} />
      <ReportViewer reportUrl={report_url} />
    </div>
  );
}
