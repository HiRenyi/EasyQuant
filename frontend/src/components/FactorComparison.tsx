import { useState, useCallback } from "react";
import { Plus, Trash2, BarChart3, Loader2 } from "lucide-react";
import type { CompareFactorsResponse, CompareFactorResult } from "../api/comparison";
import { compareFactors } from "../api/comparison";
import CorrelationMatrix from "./CorrelationMatrix";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

const METRIC_LABELS: { key: string; label: string; format: (v: number) => string; higher_better: boolean }[] = [
  { key: "sharpe", label: "Top组Sharpe", format: (v) => v.toFixed(2), higher_better: true },
  { key: "ls_sharpe", label: "多空Sharpe", format: (v) => v.toFixed(2), higher_better: true },
  { key: "monotonicity", label: "单调性", format: (v) => v.toFixed(2), higher_better: true },
  { key: "ic_mean", label: "IC均值", format: (v) => v.toFixed(4), higher_better: true },
  { key: "rank_ic_mean", label: "Rank IC", format: (v) => v.toFixed(4), higher_better: true },
  { key: "ic_ir", label: "IC_IR", format: (v) => v.toFixed(2), higher_better: true },
  { key: "spread", label: "组间价差", format: (v) => (v * 100).toFixed(2) + "%", higher_better: true },
  { key: "turnover", label: "换手率", format: (v) => (v * 100).toFixed(1) + "%", higher_better: false },
];

interface Props {
  savedExpressions?: string[];
}

export default function FactorComparison({ savedExpressions }: Props) {
  const [factors, setFactors] = useState([
    { expression: "", label: "" },
    { expression: "", label: "" },
  ]);
  const [result, setResult] = useState<CompareFactorsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [settings] = useState({
    universe: "hs300",
    start_date: "2023-01-01",
    end_date: "2025-12-31",
  });

  const updateFactor = (idx: number, field: "expression" | "label", value: string) => {
    setFactors((prev) => prev.map((f, i) => i === idx ? { ...f, [field]: value } : f));
  };

  const addFactor = () => {
    if (factors.length >= 6) return;
    setFactors((prev) => [...prev, { expression: "", label: "" }]);
  };

  const removeFactor = (idx: number) => {
    if (factors.length <= 2) return;
    setFactors((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleCompare = useCallback(async () => {
    const valid = factors.filter((f) => f.expression.trim());
    if (valid.length < 2) {
      alert("至少需要2个因子表达式");
      return;
    }
    setLoading(true);
    try {
      const data = await compareFactors(
        valid.map((f) => ({ expression: f.expression, label: f.label || undefined })),
        settings,
      );
      setResult(data);
    } catch (err) {
      alert(err instanceof Error ? err.message : "对比失败");
    } finally {
      setLoading(false);
    }
  }, [factors, settings]);

  return (
    <div className="space-y-4">
      {/* Factor inputs */}
      <div className="space-y-2">
        {factors.map((f, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: COLORS[i % COLORS.length] }}
            />
            <input
              type="text"
              value={f.label}
              onChange={(e) => updateFactor(i, "label", e.target.value)}
              placeholder={`因子${i + 1}`}
              className="w-20 rounded-lg border border-gray-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <input
              type="text"
              value={f.expression}
              onChange={(e) => updateFactor(i, "expression", e.target.value)}
              placeholder="因子表达式"
              className="flex-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              list={savedExpressions ? `cmp-expr-${i}` : undefined}
            />
            {savedExpressions && (
              <datalist id={`cmp-expr-${i}`}>
                {savedExpressions.map((e) => <option key={e} value={e} />)}
              </datalist>
            )}
            <button
              onClick={() => removeFactor(i)}
              disabled={factors.length <= 2}
              className="p-1 text-gray-400 hover:text-red-500 disabled:opacity-30"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button onClick={addFactor} disabled={factors.length >= 6} className="text-xs text-blue-600 hover:text-blue-700 disabled:opacity-50 flex items-center gap-1">
          <Plus className="h-3 w-3" /> 添加因子
        </button>
        <button
          onClick={handleCompare}
          disabled={loading || factors.filter((f) => f.expression.trim()).length < 2}
          className="ml-auto flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BarChart3 className="h-3.5 w-3.5" />}
          {loading ? "对比中..." : "开始对比"}
        </button>
      </div>

      {/* Results */}
      {result && <ComparisonResults data={result} />}
    </div>
  );
}

function ComparisonResults({ data }: { data: CompareFactorsResponse }) {
  const successFactors = data.factors.filter((f): f is CompareFactorResult & { metrics: NonNullable<CompareFactorResult["metrics"]> } =>
    f.status === "success" && !!f.metrics
  );

  if (successFactors.length === 0) {
    return <div className="text-center py-4 text-xs text-gray-400">所有因子回测均失败</div>;
  }

  return (
    <div className="space-y-4">
      {/* Metrics comparison table */}
      <div className="rounded-lg border border-gray-200 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-3 py-2 font-medium text-gray-500">指标</th>
              {successFactors.map((f, i) => (
                <th key={i} className="text-right px-3 py-2 font-medium" style={{ color: COLORS[i % COLORS.length] }}>
                  {f.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {METRIC_LABELS.map(({ key, label, format, higher_better }) => {
              const values = successFactors.map((f) => f.metrics[key as keyof typeof f.metrics] ?? 0);
              const best = higher_better ? Math.max(...values) : Math.min(...values);
              return (
                <tr key={key}>
                  <td className="px-3 py-2 text-gray-600">{label}</td>
                  {successFactors.map((f, i) => {
                    const v = f.metrics[key as keyof typeof f.metrics] ?? 0;
                    const isBest = v === best && successFactors.length > 1;
                    return (
                      <td key={i} className={`text-right px-3 py-2 font-mono ${isBest ? "font-bold text-emerald-600" : "text-gray-700"}`}>
                        {format(v)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Cumulative returns chart (simple text-based, since no chart lib) */}
      <div className="rounded-lg border border-gray-200 p-4 bg-white">
        <h4 className="text-xs font-medium text-gray-600 mb-3">Top组累计收益对比</h4>
        <div className="space-y-2">
          {successFactors.map((f, i) => {
            const rets = f.cumulative_returns ?? [];
            const finalVal = rets.length > 0 ? rets[rets.length - 1].value : 1;
            const totalReturn = ((finalVal - 1) * 100).toFixed(1);
            const maxVal = rets.length > 0 ? Math.max(...rets.map((r) => r.value)) : 1;
            const barWidth = finalVal > 0 ? Math.min(100, (finalVal / maxVal) * 80) : 0;
            return (
              <div key={i} className="flex items-center gap-3">
                <span className="text-xs w-24 truncate" style={{ color: COLORS[i % COLORS.length] }} title={f.label}>
                  {f.label}
                </span>
                <div className="flex-1 bg-gray-100 rounded-full h-4 relative overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${barWidth}%`,
                      backgroundColor: COLORS[i % COLORS.length],
                      opacity: 0.7,
                    }}
                  />
                </div>
                <span className={`text-xs font-mono w-16 text-right ${Number(totalReturn) >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                  {Number(totalReturn) >= 0 ? "+" : ""}{totalReturn}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Correlation matrix */}
      {data.correlation && (
        <div className="rounded-lg border border-gray-200 p-4 bg-white">
          <h4 className="text-xs font-medium text-gray-600 mb-3">因子相关性矩阵</h4>
          <CorrelationMatrix
            labels={data.correlation.labels}
            matrix={data.correlation.matrix}
          />
          <p className="text-[10px] text-gray-400 mt-2">高相关（&gt;0.5）因子提供相似信息，组合时应降低权重</p>
        </div>
      )}
    </div>
  );
}
