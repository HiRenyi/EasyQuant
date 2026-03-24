import { useState, useMemo } from "react";
import type { StockFactorData, StockFactorInfo } from "../types/backtest";
import { useColorMode } from "../contexts/ColorModeContext";

interface Props {
  data: StockFactorData;
  topGroupAnnualReturn: number;
  expression?: string;
}

function pct(n: number): string {
  return (n * 100).toFixed(2) + "%";
}

function SignalBar({ value, isDark }: { value: number; isDark: boolean }) {
  const width = Math.min(Math.max(value * 100, 0), 100);
  const color =
    width >= 80
      ? "bg-emerald-500"
      : width >= 50
        ? "bg-blue-500"
        : "bg-gray-400";
  return (
    <div className="flex items-center gap-2">
      <div className={`flex-1 h-2 ${isDark ? "bg-gray-800" : "bg-gray-100"} rounded-full overflow-hidden`}>
        <div className={`h-full rounded-full ${color}`} style={{ width: `${width}%` }} />
      </div>
      <span className={`text-xs ${isDark ? "text-gray-400" : "text-gray-600"} w-12 text-right tabular-nums`}>{pct(value)}</span>
    </div>
  );
}

function generateStockInterpretation(
  stock: StockFactorInfo,
  flipped: boolean,
  topGroupAnnualReturn: number,
): string {
  const rankPct = Math.round(stock.factor_rank * 100);
  const isTop = flipped ? stock.group_label === "G5" : stock.group_label === "G1";
  const isBottom = flipped ? stock.group_label === "G1" : stock.group_label === "G5";
  const returnStr = stock.period_return >= 0
    ? `上涨 ${pct(stock.period_return)}`
    : `下跌 ${pct(Math.abs(stock.period_return))}`;

  let signal = "";
  if (isTop) {
    signal = `该股票因子信号强度处于前 ${100 - rankPct}%，属于强信号区间（${stock.group_label} 组）。`;
  } else if (isBottom) {
    signal = `该股票因子信号强度处于后 ${rankPct}%，属于弱信号区间（${stock.group_label} 组）。`;
  } else {
    signal = `该股票因子信号强度处于中间区间（${stock.group_label} 组，强度 ${rankPct}%）。`;
  }

  const returnContext = `回测期间该股票累计${returnStr}，同期因子 Top 组年化收益为 ${pct(topGroupAnnualReturn)}。`;

  let guidance = "";
  if (isTop) {
    guidance = `根据因子历史表现，该组别股票平均表现优于大盘。但历史规律不代表未来，需结合当前市场环境判断。`;
  } else if (isBottom) {
    guidance = `该股票在此因子下信号偏弱，历史上该组别表现相对落后。若使用此因子策略，该股票通常不在优选范围内。`;
  } else {
    guidance = `该股票处于中间分组，因子信号不强不弱，历史上该组别表现接近市场平均水平。`;
  }

  return `${signal} ${returnContext} ${guidance}`;
}

export default function StockFactorPanel({ data, topGroupAnnualReturn }: Props) {
  const { positiveClass, negativeClass, isDark } = useColorMode();
  const [leaderboardOpen, setLeaderboardOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // Top 10 by factor_rank descending (rank already handles flipped direction)
  const top10 = useMemo(() => {
    return [...data.stocks]
      .sort((a, b) => b.factor_rank - a.factor_rank)
      .slice(0, 10);
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
      <div className={`rounded-xl border ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"} overflow-hidden`}>
        <button
          onClick={() => setLeaderboardOpen(!leaderboardOpen)}
          className={`w-full px-4 py-3 flex items-center justify-between border-b ${isDark ? "border-gray-700 bg-gray-800 hover:bg-gray-700" : "border-gray-100 bg-gray-50/50 hover:bg-gray-50"} transition-colors`}
        >
          <div className="flex items-center gap-2">
            <h4 className={`text-sm font-medium ${isDark ? "text-gray-300" : "text-gray-700"}`}>
              因子信号强度 Top 10
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
              <thead className={`sticky top-0 ${isDark ? "bg-gray-900" : "bg-white"} z-10`}>
                <tr className={`border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                  <th className={`px-4 py-2.5 text-left font-medium ${isDark ? "text-gray-400" : "text-gray-500"} w-12`}>#</th>
                  <th className={`px-4 py-2.5 text-left font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>股票代码</th>
                  <th className={`px-4 py-2.5 font-medium ${isDark ? "text-gray-400" : "text-gray-500"} text-left`} style={{ minWidth: 160 }}>
                    信号强度
                  </th>
                  <th className={`px-4 py-2.5 text-right font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>所在分组</th>
                </tr>
              </thead>
              <tbody>
                {top10.map((s, i) => (
                  <tr
                    key={s.stock_code}
                    className={`border-b ${isDark ? "border-gray-800 last:border-0 hover:bg-gray-800/50" : "border-gray-50 last:border-0 hover:bg-gray-50/50"}`}
                  >
                    <td className="px-4 py-2 text-gray-400 text-xs">{i + 1}</td>
                    <td className={`px-4 py-2 font-mono ${isDark ? "text-gray-300" : "text-gray-700"}`}>{s.stock_code}</td>
                    <td className="px-4 py-2">
                      <SignalBar value={s.factor_rank} isDark={isDark} />
                    </td>
                    <td className={`px-4 py-2 text-right ${isDark ? "text-gray-400" : "text-gray-500"}`}>{s.group_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Area B — Individual Stock Factor Profile */}
      <div className={`rounded-xl border ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"} overflow-hidden`}>
        <div className={`px-4 py-3 border-b ${isDark ? "border-gray-700 bg-gray-800" : "border-gray-100 bg-gray-50/50"}`}>
          <h4 className={`text-sm font-medium ${isDark ? "text-gray-300" : "text-gray-700"} mb-2`}>个股因子画像</h4>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="输入股票代码查看 AI 因子画像，如 sh.600519"
            className={`w-full px-3 py-2 text-sm border ${isDark ? "border-gray-700 bg-gray-900 text-gray-100 placeholder-gray-500 focus:ring-amber-500/20 focus:border-amber-400" : "border-gray-200 bg-white placeholder-gray-400 focus:ring-blue-500/20 focus:border-blue-400"} rounded-lg focus:outline-none focus:ring-2`}
          />
        </div>

        {searchResult && (
          <div className="px-4 py-4 space-y-4">
            {/* Factor Score */}
            <div>
              <p className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-500"} mb-1.5`}>因子打分</p>
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <SignalBar value={searchResult.factor_rank} isDark={isDark} />
                </div>
                <span className={`text-sm font-medium ${isDark ? "text-gray-300" : "text-gray-700"}`}>
                  {searchResult.group_label}
                </span>
              </div>
              <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"} mt-1`}>
                信号强度 {pct(searchResult.factor_rank)}，位于 {searchResult.group_label} 组
              </p>
            </div>

            {/* AI Signal Interpretation */}
            <div className={`rounded-lg ${isDark ? "bg-amber-500/10 border border-amber-500/20" : "bg-blue-50 border border-blue-100"} px-3 py-2.5`}>
              <p className={`text-xs font-medium ${isDark ? "text-amber-400" : "text-blue-600"} mb-1`}>信号解读</p>
              <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-600"} leading-relaxed`}>
                {generateStockInterpretation(
                  searchResult,
                  data.flipped,
                  topGroupAnnualReturn,
                )}
              </p>
              <p className="text-[10px] text-gray-400 mt-1.5">基于历史回测数据，不构成投资建议</p>
            </div>

            {/* Return Contribution */}
            <div>
              <p className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-500"} mb-1`}>回测期收益</p>
              <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-600"}`}>
                累计{" "}
                <span className={searchResult.period_return >= 0 ? `${positiveClass} font-medium` : `${negativeClass} font-medium`}>
                  {searchResult.period_return >= 0 ? "+" : ""}{pct(searchResult.period_return)}
                </span>
                {" "}· Top 组年化{" "}
                <span className={topGroupAnnualReturn >= 0 ? `${positiveClass} font-medium` : `${negativeClass} font-medium`}>
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
