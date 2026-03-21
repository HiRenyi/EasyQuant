import { useState } from "react";
import type { FactorItem } from "../api/composite";
import {
  fetchFactorAttribution,
  type AttributionResult,
} from "../api/composite";
import { pct, num } from "../utils/format";
import CorrelationMatrix from "./CorrelationMatrix";

interface Props {
  factors: FactorItem[];
  compositeExpression?: string;
  universe: string;
  startDate: string;
  endDate: string;
  nGroups: number;
  holdingPeriod: number;
}

export default function AttributionChart({
  factors,
  compositeExpression,
  universe,
  startDate,
  endDate,
  nGroups,
  holdingPeriod,
}: Props) {
  const [result, setResult] = useState<AttributionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFactorAttribution({
        factors,
        composite_expression: compositeExpression,
        universe,
        start_date: startDate,
        end_date: endDate,
        n_groups: nGroups,
        holding_period: holdingPeriod,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "归因分析失败");
    } finally {
      setLoading(false);
    }
  };

  if (!result) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-white p-5 text-center">
        <p className="text-sm text-gray-500 mb-3">分析各子因子对组合的贡献度</p>
        <button
          onClick={handleRun}
          disabled={loading || factors.length < 2}
          className="inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50 transition-colors"
        >
          {loading ? (
            <>
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              分析中...
            </>
          ) : (
            "运行归因分析"
          )}
        </button>
        {error && <p className="mt-2 text-xs text-red-500">{error}</p>}
      </div>
    );
  }

  const successFactors = result.factors.filter((f) => f.status === "success");
  const maxIcMean = Math.max(...successFactors.map((f) => Math.abs(f.ic_mean ?? 0)), 0.001);

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h3 className="text-sm font-medium text-gray-700">因子归因分析</h3>
        <button
          onClick={handleRun}
          disabled={loading}
          className="text-xs text-purple-600 hover:text-purple-800"
        >
          {loading ? "分析中..." : "重新分析"}
        </button>
      </div>

      {/* Factor metrics table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-gray-500 text-xs">
              <th className="px-3 py-2 text-left">因子</th>
              <th className="px-3 py-2 text-center">IC均值</th>
              <th className="px-3 py-2 text-center">IC_IR</th>
              <th className="px-3 py-2 text-center">Sharpe</th>
              <th className="px-3 py-2 text-center">单调性</th>
              <th className="px-3 py-2 text-center">换手率</th>
              <th className="px-3 py-2 text-left w-32">IC 强度</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {result.factors.map((f, i) => (
              <tr key={i} className={f.status === "failed" ? "text-gray-400" : ""}>
                <td className="px-3 py-2 text-xs font-medium">{f.label}</td>
                {f.status === "success" ? (
                  <>
                    <td className="px-3 py-2 text-center text-xs">{num(f.ic_mean ?? 0)}</td>
                    <td className="px-3 py-2 text-center text-xs">{num(f.ic_ir ?? 0)}</td>
                    <td className="px-3 py-2 text-center text-xs">{num(f.sharpe ?? 0)}</td>
                    <td className="px-3 py-2 text-center text-xs">{num(f.monotonicity ?? 0)}</td>
                    <td className="px-3 py-2 text-center text-xs">{pct(f.turnover ?? 0)}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${(f.ic_mean ?? 0) >= 0 ? "bg-emerald-500" : "bg-red-400"}`}
                            style={{ width: `${Math.min(Math.abs(f.ic_mean ?? 0) / maxIcMean * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                  </>
                ) : (
                  <td colSpan={6} className="px-3 py-2 text-xs text-red-400">{f.error}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Marginal contributions */}
      {result.contributions.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-100">
          <p className="text-xs text-gray-500 mb-2">边际 IC 贡献（Leave-One-Out）</p>
          <div className="space-y-1.5">
            {result.contributions.map((c, i) => {
              const maxContrib = Math.max(
                ...result.contributions.map((x) => Math.abs(x.marginal_ic)),
                0.0001
              );
              const barWidth = Math.min(Math.abs(c.marginal_ic) / maxContrib * 100, 100);
              const isPositive = c.marginal_ic >= 0;
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="w-24 truncate text-gray-600">{c.label}</span>
                  <div className="flex-1 flex items-center gap-1">
                    <div className="flex-1 h-3 bg-gray-50 rounded relative">
                      <div
                        className={`absolute top-0 h-full rounded ${isPositive ? "bg-emerald-400" : "bg-red-400"}`}
                        style={{
                          width: `${barWidth}%`,
                          [isPositive ? "left" : "right"]: 0,
                        }}
                      />
                    </div>
                  </div>
                  <span className={`w-20 text-right font-mono ${isPositive ? "text-emerald-600" : "text-red-500"}`}>
                    {c.marginal_ic >= 0 ? "+" : ""}{num(c.marginal_ic)}
                  </span>
                  {c.contribution_pct !== undefined && (
                    <span className="w-14 text-right text-gray-400">
                      ({c.contribution_pct > 0 ? "+" : ""}{c.contribution_pct.toFixed(1)}%)
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* IC Correlation Matrix */}
      {result.ic_correlation && (
        <div className="px-4 py-3 border-t border-gray-100">
          <p className="text-xs text-gray-500 mb-2">IC 相关性矩阵</p>
          <CorrelationMatrix
            labels={Object.keys(result.ic_correlation)}
            matrix={result.ic_correlation}
          />
        </div>
      )}

      {error && (
        <div className="px-4 py-2 text-xs text-red-500 border-t border-gray-100">{error}</div>
      )}
    </div>
  );
}
