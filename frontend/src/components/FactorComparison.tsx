import { useState, useCallback } from "react";
import { Plus, Trash2, BarChart3, Loader2, Star, Check } from "lucide-react";
import { useColorMode } from "../contexts/ColorModeContext";
import type { CompareFactorsResponse, CompareFactorResult } from "../api/comparison";
import { compareFactors } from "../api/comparison";
import type { SavedFactor } from "../api/factorLibrary";
import { fetchFactors } from "../api/factorLibrary";
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
  { key: "wq_fitness", label: "WQ Fitness", format: (v) => v.toFixed(2), higher_better: true },
];

interface Props {
  savedExpressions?: string[];
}

export default function FactorComparison({ savedExpressions }: Props) {
  const { positiveClass, negativeClass, isDark } = useColorMode();
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

  // Factor library picker
  const [showPicker, setShowPicker] = useState(false);
  const [libraryFactors, setLibraryFactors] = useState<SavedFactor[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerSelected, setPickerSelected] = useState<Set<string>>(new Set());

  const openPicker = useCallback(async () => {
    setShowPicker(true);
    setPickerSelected(new Set());
    setPickerLoading(true);
    try {
      const data = await fetchFactors();
      setLibraryFactors(data);
    } catch {
      setLibraryFactors([]);
    } finally {
      setPickerLoading(false);
    }
  }, []);

  const togglePickerItem = (expr: string) => {
    setPickerSelected((prev) => {
      const next = new Set(prev);
      if (next.has(expr)) next.delete(expr); else next.add(expr);
      return next;
    });
  };

  const confirmPicker = () => {
    if (pickerSelected.size === 0) { setShowPicker(false); return; }
    const existing = new Set(factors.map((f) => f.expression).filter(Boolean));
    const newItems: { expression: string; label: string }[] = [];
    for (const expr of pickerSelected) {
      if (!existing.has(expr)) {
        newItems.push({ expression: expr, label: "" });
      }
    }
    if (newItems.length > 0) {
      setFactors((prev) => {
        const result = [...prev];
        let newIdx = 0;
        for (let i = 0; i < result.length && newIdx < newItems.length; i++) {
          if (!result[i].expression.trim()) {
            result[i] = newItems[newIdx++];
          }
        }
        while (newIdx < newItems.length && result.length < 6) {
          result.push(newItems[newIdx++]);
        }
        return result;
      });
    }
    setShowPicker(false);
  };

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
              className={`w-20 rounded-lg border ${isDark ? "border-gray-700 bg-gray-800 text-gray-100" : "border-gray-200"} px-2 py-1.5 text-xs focus:outline-none focus:ring-2 ${isDark ? "focus:ring-amber-500/20" : "focus:ring-blue-500/20"}`}
            />
            <input
              type="text"
              value={f.expression}
              onChange={(e) => updateFactor(i, "expression", e.target.value)}
              placeholder="因子表达式"
              className={`flex-1 rounded-lg border ${isDark ? "border-gray-700 bg-gray-800 text-gray-100" : "border-gray-200"} px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-2 ${isDark ? "focus:ring-amber-500/20" : "focus:ring-blue-500/20"}`}
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
        <button onClick={addFactor} disabled={factors.length >= 6} className={`text-xs ${isDark ? "text-amber-400 hover:text-amber-300" : "text-blue-600 hover:text-blue-700"} disabled:opacity-50 flex items-center gap-1`}>
          <Plus className="h-3 w-3" /> 添加因子
        </button>
        <button
          onClick={openPicker}
          className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700"
        >
          <Star className="h-3 w-3" /> 从因子库选择
        </button>
        <button
          onClick={handleCompare}
          disabled={loading || factors.filter((f) => f.expression.trim()).length < 2}
          className={`ml-auto flex items-center gap-1.5 rounded-lg ${isDark ? "bg-amber-500 hover:bg-amber-600" : "bg-blue-600 hover:bg-blue-700"} px-4 py-2 text-xs font-medium text-white disabled:opacity-50`}
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BarChart3 className="h-3.5 w-3.5" />}
          {loading ? "对比中..." : "开始对比"}
        </button>
      </div>

      {/* Factor library picker modal */}
      {showPicker && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setShowPicker(false)}
        >
          <div
            className={`${isDark ? "bg-gray-900" : "bg-white"} rounded-2xl shadow-xl w-full max-w-lg mx-4 max-h-[70vh] flex flex-col`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={`flex items-center justify-between px-5 py-3 border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
              <div>
                <h3 className={`text-sm font-semibold ${isDark ? "text-gray-100" : "text-gray-900"}`}>从因子库选择</h3>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  勾选要对比的因子{pickerSelected.size > 0 && `（已选 ${pickerSelected.size} 个）`}
                </p>
              </div>
              <button
                onClick={confirmPicker}
                disabled={pickerSelected.size === 0}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg ${isDark ? "bg-amber-500 hover:bg-amber-600" : "bg-blue-600 hover:bg-blue-700"} text-white text-xs font-medium disabled:opacity-50 transition-colors`}
              >
                <Check className="h-3.5 w-3.5" />
                确认添加
              </button>
            </div>
            <div className="overflow-y-auto px-5 py-3 space-y-1.5">
              {pickerLoading ? (
                <div className="text-center py-8 text-xs text-gray-400">
                  <Loader2 className="h-4 w-4 animate-spin inline mr-1" />加载中...
                </div>
              ) : libraryFactors.length === 0 ? (
                <div className="text-center py-8">
                  <Star className={`h-8 w-8 ${isDark ? "text-gray-600" : "text-gray-200"} mx-auto mb-2`} />
                  <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>因子库为空</p>
                  <p className="text-[10px] text-gray-400 mt-1">先在单因子回测页收藏因子</p>
                </div>
              ) : (
                libraryFactors.map((f) => {
                  const selected = pickerSelected.has(f.expression);
                  const alreadyInList = factors.some((x) => x.expression === f.expression);
                  const m = f.metrics;
                  return (
                    <button
                      key={f.id}
                      onClick={() => !alreadyInList && togglePickerItem(f.expression)}
                      disabled={alreadyInList}
                      className={`w-full text-left rounded-lg border px-3 py-2.5 transition-all ${
                        alreadyInList
                          ? `${isDark ? "border-gray-700 bg-gray-800" : "border-gray-100 bg-gray-50"} opacity-50 cursor-not-allowed`
                          : selected
                          ? `${isDark ? "border-amber-500 bg-amber-500/10 ring-1 ring-amber-500/30" : "border-blue-300 bg-blue-50 ring-1 ring-blue-200"}`
                          : `${isDark ? "border-gray-700 bg-gray-800 hover:border-amber-500/50 hover:shadow-sm" : "border-gray-150 bg-white hover:border-blue-200 hover:shadow-sm"}`
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                          alreadyInList ? `${isDark ? "border-gray-600 bg-gray-700" : "border-gray-300 bg-gray-200"}` :
                          selected ? `${isDark ? "border-amber-500 bg-amber-500" : "border-blue-500 bg-blue-500"}` : `${isDark ? "border-gray-600" : "border-gray-300"}`
                        }`}>
                          {(selected || alreadyInList) && <Check className="h-3 w-3 text-white" />}
                        </div>
                        <code className={`text-xs ${isDark ? "text-amber-400" : "text-blue-700"} font-mono truncate flex-1`} title={f.expression}>
                          {f.expression}
                        </code>
                        {alreadyInList && (
                          <span className="text-[10px] text-gray-400 shrink-0">已添加</span>
                        )}
                      </div>
                      {m && (
                        <div className={`flex items-center gap-2 mt-1 ml-6 text-[11px] ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                          <span>Sharpe <span className={`font-medium ${isDark ? "text-gray-300" : "text-gray-700"}`}>{m.sharpe.toFixed(2)}</span></span>
                          <span className={isDark ? "text-gray-600" : "text-gray-200"}>|</span>
                          <span className={m.cagr >= 0 ? positiveClass : negativeClass}>
                            {(m.cagr * 100).toFixed(1)}%
                          </span>
                          <span className={isDark ? "text-gray-600" : "text-gray-200"}>|</span>
                          <span className={negativeClass}>{(m.max_drawdown * 100).toFixed(1)}%</span>
                        </div>
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {result && <ComparisonResults data={result} />}
    </div>
  );
}

function ComparisonResults({ data }: { data: CompareFactorsResponse }) {
  const { positiveClass, negativeClass, isDark } = useColorMode();
  const successFactors = data.factors.filter((f): f is CompareFactorResult & { metrics: NonNullable<CompareFactorResult["metrics"]> } =>
    f.status === "success" && !!f.metrics
  );

  if (successFactors.length === 0) {
    return <div className="text-center py-4 text-xs text-gray-400">所有因子回测均失败</div>;
  }

  return (
    <div className="space-y-4">
      {/* Metrics comparison table */}
      <div className={`rounded-lg border ${isDark ? "border-gray-700" : "border-gray-200"} overflow-x-auto`}>
        <table className="w-full text-xs">
          <thead>
            <tr className={`${isDark ? "bg-gray-800 border-gray-700" : "bg-gray-50 border-gray-200"} border-b`}>
              <th className={`text-left px-3 py-2 font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>指标</th>
              {successFactors.map((f, i) => (
                <th key={i} className="text-right px-3 py-2 font-medium" style={{ color: COLORS[i % COLORS.length] }}>
                  {f.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className={`divide-y ${isDark ? "divide-gray-700" : "divide-gray-100"}`}>
            {METRIC_LABELS.map(({ key, label, format, higher_better }) => {
              const values = successFactors.map((f) => f.metrics[key as keyof typeof f.metrics] ?? 0);
              const best = higher_better ? Math.max(...values) : Math.min(...values);
              return (
                <tr key={key}>
                  <td className={`px-3 py-2 ${isDark ? "text-gray-400" : "text-gray-600"}`}>{label}</td>
                  {successFactors.map((f, i) => {
                    const v = f.metrics[key as keyof typeof f.metrics] ?? 0;
                    const isBest = v === best && successFactors.length > 1;
                    return (
                      <td key={i} className={`text-right px-3 py-2 font-mono ${isBest ? `font-bold ${positiveClass}` : `${isDark ? "text-gray-300" : "text-gray-700"}`}`}>
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
      <div className={`rounded-lg border ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"} p-4`}>
        <h4 className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-600"} mb-3`}>Top组累计收益对比</h4>
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
                <div className={`flex-1 ${isDark ? "bg-gray-800" : "bg-gray-100"} rounded-full h-4 relative overflow-hidden`}>
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${barWidth}%`,
                      backgroundColor: COLORS[i % COLORS.length],
                      opacity: 0.7,
                    }}
                  />
                </div>
                <span className={`text-xs font-mono w-16 text-right ${Number(totalReturn) >= 0 ? positiveClass : negativeClass}`}>
                  {Number(totalReturn) >= 0 ? "+" : ""}{totalReturn}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Correlation matrix */}
      {data.correlation && (
        <div className={`rounded-lg border ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"} p-4`}>
          <h4 className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-600"} mb-3`}>因子相关性矩阵</h4>
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
