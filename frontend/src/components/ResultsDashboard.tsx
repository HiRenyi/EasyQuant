import type { BacktestResult } from "../types/backtest";
import type { ReactNode } from "react";
import MetricCard from "./MetricCard";
import GroupReturnsTable from "./GroupReturnsTable";
import ReportViewer from "./ReportViewer";

interface Props {
  result: BacktestResult;
  iterationSlot?: ReactNode;
}

function pct(n: number): string {
  return (n * 100).toFixed(2) + "%";
}

function num(n: number): string {
  return n.toFixed(4);
}

export default function ResultsDashboard({ result, iterationSlot }: Props) {
  const { metrics, backtest_summary, report_url, params } = result;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">回测结果</h3>
        <span className="text-xs text-gray-400">
          {params.universe} · {params.start_date} ~ {params.end_date} · {params.stock_count} 只股票
        </span>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
        <p className="text-xs font-medium text-gray-500 mb-1">因子表达式</p>
        <code className="text-sm text-blue-700 font-mono break-all leading-relaxed">{params.expression}</code>
      </div>

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

      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="多头 Sharpe" value={num(backtest_summary.top_group_sharpe ?? backtest_summary.long_short_sharpe)} color={(backtest_summary.top_group_sharpe ?? backtest_summary.long_short_sharpe) >= 1 ? "green" : "default"} />
        <MetricCard label="单调性" value={num(backtest_summary.monotonicity_score)} />
        <MetricCard label="分组价差" value={pct(backtest_summary.spread)} color={backtest_summary.spread >= 0 ? "green" : "red"} />
      </div>

      {iterationSlot}

      <GroupReturnsTable groupReturns={backtest_summary.group_returns} />
      <ReportViewer reportUrl={report_url} />
    </div>
  );
}
