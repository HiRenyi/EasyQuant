import { useState, useMemo } from "react";
import type { StockFactorData, StockFactorInfo } from "../types/backtest";

interface Props {
  data: StockFactorData;
  topGroupAnnualReturn: number;
}

function pct(n: number): string {
  return (n * 100).toFixed(2) + "%";
}

function SignalBar({ value }: { value: number }) {
  const width = Math.min(Math.max(value * 100, 0), 100);
  const color =
    width >= 80
      ? "bg-emerald-500"
      : width >= 50
        ? "bg-blue-500"
        : "bg-gray-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${width}%` }}
        />
      </div>
      <span className="text-xs text-gray-600 w-12 text-right tabular-nums">
        {pct(value)}
      </span>
    </div>
  );
}

export default function StockFactorPanel({ data, topGroupAnnualReturn }: Props) {
  const [leaderboardOpen, setLeaderboardOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // Top 50 by factor_rank descending (rank already handles flipped direction)
  const top50 = useMemo(() => {
    return [...data.stocks]
      .sort((a, b) => b.factor_rank - a.factor_rank)
      .slice(0, 50);
  }, [data.stocks]);

  // Stock search
  const searchResult: StockFactorInfo | null = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return null;
    return data.stocks.find((s) => s.stock_code.toLowerCase() === q) ?? null;
  }, [searchQuery, data.stocks]);

  const noMatch = searchQuery.trim().length > 0 && searchResult === null;

  return (
    <div className="space-y-4">
      {/* Area A — Signal Strength Leaderboard */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <button
          onClick={() => setLeaderboardOpen(!leaderboardOpen)}
          className="w-full px-4 py-3 flex items-center justify-between border-b border-gray-100 bg-gray-50/50 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-medium text-gray-700">
              因子信号强度 Top 50
            </h4>
            <span className="text-xs text-gray-400">
              调仓日 {data.rebalance_date} · 共 {data.total_stock_count} 只股票
            </span>
          </div>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${leaderboardOpen ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {leaderboardOpen && (
          <div className="max-h-[520px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white z-10">
                <tr className="border-b border-gray-100">
                  <th className="px-4 py-2.5 text-left font-medium text-gray-500 w-12">#</th>
                  <th className="px-4 py-2.5 text-left font-medium text-gray-500">股票代码</th>
                  <th className="px-4 py-2.5 font-medium text-gray-500 text-left" style={{ minWidth: 160 }}>
                    信号强度
                  </th>
                  <th className="px-4 py-2.5 text-right font-medium text-gray-500">所在分组</th>
                </tr>
              </thead>
              <tbody>
                {top50.map((s, i) => (
                  <tr
                    key={s.stock_code}
                    className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50"
                  >
                    <td className="px-4 py-2 text-gray-400 text-xs">{i + 1}</td>
                    <td className="px-4 py-2 font-mono text-gray-700">{s.stock_code}</td>
                    <td className="px-4 py-2">
                      <SignalBar value={s.factor_rank} />
                    </td>
                    <td className="px-4 py-2 text-right text-gray-500">{s.group_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Area B — Individual Stock Factor Profile */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
          <h4 className="text-sm font-medium text-gray-700 mb-2">个股因子画像</h4>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="输入股票代码查看 AI 因子画像，如 sh.600519"
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 bg-white placeholder-gray-400"
          />
        </div>

        {searchResult && (
          <div className="px-4 py-4 space-y-4">
            {/* Factor Score */}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1.5">因子打分</p>
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <SignalBar value={searchResult.factor_rank} />
                </div>
                <span className="text-sm font-medium text-gray-700">
                  {searchResult.group_label}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                信号强度 {pct(searchResult.factor_rank)}，位于 {searchResult.group_label} 组
              </p>
            </div>

            {/* Factor Explanation */}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">因子解释</p>
              <p className="text-sm text-gray-600">
                {data.flipped
                  ? "该因子为反转型，低因子值对应更强信号"
                  : "高因子值对应更强信号"}
              </p>
            </div>

            {/* Return Contribution */}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">收益贡献</p>
              <p className="text-sm text-gray-600">
                该股票在回测期间累计收益{" "}
                <span className={searchResult.period_return >= 0 ? "text-emerald-600 font-medium" : "text-red-500 font-medium"}>
                  {searchResult.period_return >= 0 ? "+" : ""}{pct(searchResult.period_return)}
                </span>
                ，同期因子 Top 组年化{" "}
                <span className={topGroupAnnualReturn >= 0 ? "text-emerald-600 font-medium" : "text-red-500 font-medium"}>
                  {topGroupAnnualReturn >= 0 ? "+" : ""}{pct(topGroupAnnualReturn)}
                </span>
              </p>
            </div>
          </div>
        )}

        {noMatch && (
          <div className="px-4 py-6 text-center text-sm text-gray-400">
            该股票不在本次回测的股票池中
          </div>
        )}
      </div>

      {/* Compliance Disclaimer */}
      <p className="text-xs text-gray-400 text-center leading-relaxed">
        以上数据基于历史因子回测，仅供研究参考，不构成任何投资建议。市场有风险，投资需谨慎。
      </p>
    </div>
  );
}
