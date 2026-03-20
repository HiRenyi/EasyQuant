import { useState } from "react";
import type { StockRecommendations as StockRecommendationsType } from "../types/backtest";

interface Props {
  recommendations: StockRecommendationsType;
}

function fmt(n: number, pct = false): string {
  if (pct) return (n * 100).toFixed(2) + "%";
  return n.toFixed(4);
}

export default function StockRecommendations({ recommendations }: Props) {
  const [expanded, setExpanded] = useState(false);
  const {
    rebalance_date,
    top_group_label,
    flipped,
    stock_count,
    total_stock_count,
    top_group_stocks,
    all_stocks_ranking,
  } = recommendations;

  const topGroupSet = new Set(top_group_stocks.map((s) => s.stock_code));

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium text-gray-700">
            个股推荐持仓
          </h4>
          <span className="text-xs text-gray-400">
            调仓日 {rebalance_date}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {top_group_label} 组 · {stock_count} 只股票 · 等权 {fmt(1 / stock_count, true)}/只
          {flipped && (
            <span className="ml-2 text-amber-600">
              (因子反转：低因子值 = 高排名)
            </span>
          )}
        </p>
      </div>

      {/* Top group table */}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="px-4 py-2.5 text-left font-medium text-gray-500">股票代码</th>
            <th className="px-4 py-2.5 text-right font-medium text-gray-500">因子值</th>
            <th className="px-4 py-2.5 text-right font-medium text-gray-500">百分位排名</th>
            <th className="px-4 py-2.5 text-right font-medium text-gray-500">权重</th>
          </tr>
        </thead>
        <tbody>
          {top_group_stocks.map((s) => (
            <tr key={s.stock_code} className="border-b border-gray-50 last:border-0">
              <td className="px-4 py-2 font-mono text-gray-700">{s.stock_code}</td>
              <td className="px-4 py-2 text-right text-gray-700">{fmt(s.factor_value)}</td>
              <td className="px-4 py-2 text-right text-emerald-600">{fmt(s.factor_rank, true)}</td>
              <td className="px-4 py-2 text-right text-gray-700">{fmt(s.weight, true)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Expand toggle */}
      <div className="border-t border-gray-100">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full px-4 py-2.5 text-xs text-gray-500 hover:bg-gray-50 transition-colors flex items-center justify-center gap-1"
        >
          {expanded ? "收起" : `查看全部 ${total_stock_count} 只股票排名`}
          <svg
            className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* All stocks ranking (collapsed by default) */}
      {expanded && (
        <div className="border-t border-gray-100 max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white">
              <tr className="border-b border-gray-100">
                <th className="px-4 py-2.5 text-left font-medium text-gray-500">股票代码</th>
                <th className="px-4 py-2.5 text-right font-medium text-gray-500">因子值</th>
                <th className="px-4 py-2.5 text-right font-medium text-gray-500">百分位排名</th>
                <th className="px-4 py-2.5 text-right font-medium text-gray-500">分组</th>
              </tr>
            </thead>
            <tbody>
              {all_stocks_ranking.map((s) => (
                <tr
                  key={s.stock_code}
                  className={`border-b border-gray-50 last:border-0 ${
                    topGroupSet.has(s.stock_code) ? "bg-emerald-50/50" : ""
                  }`}
                >
                  <td className="px-4 py-2 font-mono text-gray-700">{s.stock_code}</td>
                  <td className="px-4 py-2 text-right text-gray-700">{fmt(s.factor_value)}</td>
                  <td className={`px-4 py-2 text-right ${
                    topGroupSet.has(s.stock_code) ? "text-emerald-600" : "text-gray-700"
                  }`}>
                    {fmt(s.factor_rank, true)}
                  </td>
                  <td className="px-4 py-2 text-right text-gray-500">{s.group_label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
