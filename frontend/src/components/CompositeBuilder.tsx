import { useState, useCallback } from "react";
import { Plus, Trash2, Play, Loader2, Shuffle, Star, Check } from "lucide-react";
import type { FactorItem, CompositeBacktestPayload } from "../api/composite";
import type { SavedFactor } from "../api/factorLibrary";
import { fetchFactors } from "../api/factorLibrary";
import AttributionChart from "./AttributionChart";

interface Props {
  onSubmit: (payload: CompositeBacktestPayload) => void;
  isLoading: boolean;
  savedExpressions?: string[];
}

const METHODS = [
  { value: "weighted_rank", label: "加权排名", desc: "各因子截面排名后加权求和（推荐）" },
  { value: "weighted_zscore", label: "加权Z-Score", desc: "各因子标准化后加权求和" },
  { value: "equal_weight", label: "等权", desc: "忽略权重，各因子等权组合" },
];

export default function CompositeBuilder({ onSubmit, isLoading, savedExpressions }: Props) {
  const [factors, setFactors] = useState<FactorItem[]>([
    { expression: "", weight: 1.0 },
    { expression: "", weight: 1.0 },
  ]);
  const [method, setMethod] = useState("weighted_rank");
  const [settings, setSettings] = useState({
    universe: "hs300",
    start_date: "2023-01-01",
    end_date: "2025-12-31",
    n_groups: 5,
    holding_period: 5,
    benchmark: "hs300",
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
    // Existing non-empty expressions
    const existing = new Set(factors.map((f) => f.expression).filter(Boolean));
    const newItems: FactorItem[] = [];
    for (const expr of pickerSelected) {
      if (!existing.has(expr)) {
        newItems.push({ expression: expr, weight: 1.0 });
      }
    }
    if (newItems.length > 0) {
      setFactors((prev) => {
        // Fill empty slots first, then append
        const result = [...prev];
        let newIdx = 0;
        for (let i = 0; i < result.length && newIdx < newItems.length; i++) {
          if (!result[i].expression.trim()) {
            result[i] = newItems[newIdx++];
          }
        }
        // Append remaining
        while (newIdx < newItems.length && result.length < 10) {
          result.push(newItems[newIdx++]);
        }
        return result;
      });
    }
    setShowPicker(false);
  };

  const updateFactor = (idx: number, field: keyof FactorItem, value: string | number) => {
    setFactors((prev) => prev.map((f, i) => i === idx ? { ...f, [field]: value } : f));
  };

  const addFactor = () => {
    if (factors.length >= 10) return;
    setFactors((prev) => [...prev, { expression: "", weight: 1.0 }]);
  };

  const removeFactor = (idx: number) => {
    if (factors.length <= 2) return;
    setFactors((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = useCallback(() => {
    const validFactors = factors.filter((f) => f.expression.trim());
    if (validFactors.length < 2) {
      alert("至少需要2个有效因子表达式");
      return;
    }
    onSubmit({
      factors: validFactors,
      combination_method: method,
      ...settings,
    });
  }, [factors, method, settings, onSubmit]);

  const totalWeight = factors.reduce((s, f) => s + f.weight, 0);

  return (
    <div className="space-y-4">
      {/* Factor list */}
      <div className="space-y-2">
        {factors.map((f, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="text-xs text-gray-400 w-6 shrink-0 text-right">{i + 1}.</span>
            <div className="flex-1 relative">
              <input
                type="text"
                value={f.expression}
                onChange={(e) => updateFactor(i, "expression", e.target.value)}
                placeholder="输入因子表达式，如 rank(close/ts_mean(close, 20))"
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                list={savedExpressions ? `saved-expr-${i}` : undefined}
              />
              {savedExpressions && savedExpressions.length > 0 && (
                <datalist id={`saved-expr-${i}`}>
                  {savedExpressions.map((e) => (
                    <option key={e} value={e} />
                  ))}
                </datalist>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <input
                type="number"
                min={0}
                max={10}
                step={0.1}
                value={f.weight}
                onChange={(e) => updateFactor(i, "weight", Number(e.target.value))}
                className="w-16 rounded-lg border border-gray-200 px-2 py-2 text-xs text-center focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                title="权重"
              />
              <span className="text-[10px] text-gray-400 w-8">
                {totalWeight > 0 ? `${((f.weight / totalWeight) * 100).toFixed(0)}%` : "—"}
              </span>
            </div>
            <button
              onClick={() => removeFactor(i)}
              disabled={factors.length <= 2}
              className="p-1.5 rounded text-gray-400 hover:text-red-500 disabled:opacity-30 disabled:cursor-not-allowed"
              title="删除"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={addFactor}
          disabled={factors.length >= 10}
          className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 disabled:opacity-50"
        >
          <Plus className="h-3.5 w-3.5" />
          添加因子 ({factors.length}/10)
        </button>
        <button
          onClick={openPicker}
          className="flex items-center gap-1.5 text-xs text-amber-600 hover:text-amber-700"
        >
          <Star className="h-3.5 w-3.5" />
          从因子库选择
        </button>
      </div>

      {/* Factor library picker modal */}
      {showPicker && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setShowPicker(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 max-h-[70vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">从因子库选择</h3>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  勾选要加入组合的因子{pickerSelected.size > 0 && `（已选 ${pickerSelected.size} 个）`}
                </p>
              </div>
              <button
                onClick={confirmPicker}
                disabled={pickerSelected.size === 0}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
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
                  <Star className="h-8 w-8 text-gray-200 mx-auto mb-2" />
                  <p className="text-xs text-gray-500">因子库为空</p>
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
                          ? "border-gray-100 bg-gray-50 opacity-50 cursor-not-allowed"
                          : selected
                          ? "border-blue-300 bg-blue-50 ring-1 ring-blue-200"
                          : "border-gray-150 bg-white hover:border-blue-200 hover:shadow-sm"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                          alreadyInList ? "border-gray-300 bg-gray-200" :
                          selected ? "border-blue-500 bg-blue-500" : "border-gray-300"
                        }`}>
                          {(selected || alreadyInList) && <Check className="h-3 w-3 text-white" />}
                        </div>
                        <code className="text-xs text-blue-700 font-mono truncate flex-1" title={f.expression}>
                          {f.expression}
                        </code>
                        {alreadyInList && (
                          <span className="text-[10px] text-gray-400 shrink-0">已添加</span>
                        )}
                      </div>
                      {m && (
                        <div className="flex items-center gap-2 mt-1 ml-6 text-[11px] text-gray-500">
                          <span>Sharpe <span className="font-medium text-gray-700">{m.sharpe.toFixed(2)}</span></span>
                          <span className="text-gray-200">|</span>
                          <span className={m.cagr >= 0 ? "text-emerald-600" : "text-red-500"}>
                            {(m.cagr * 100).toFixed(1)}%
                          </span>
                          <span className="text-gray-200">|</span>
                          <span className="text-red-500">{(m.max_drawdown * 100).toFixed(1)}%</span>
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

      {/* Method selection */}
      <div className="flex gap-2">
        {METHODS.map((m) => (
          <button
            key={m.value}
            onClick={() => setMethod(m.value)}
            className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
              method === m.value
                ? "bg-blue-50 text-blue-700 ring-1 ring-blue-200"
                : "bg-gray-50 text-gray-500 hover:bg-gray-100"
            }`}
            title={m.desc}
          >
            <Shuffle className="h-3 w-3 inline mr-1" />
            {m.label}
          </button>
        ))}
      </div>

      {/* Compact settings */}
      <div className="grid grid-cols-3 gap-2">
        <select
          value={settings.universe}
          onChange={(e) => setSettings((s) => ({ ...s, universe: e.target.value }))}
          className="rounded-lg border border-gray-200 px-2 py-1.5 text-xs"
        >
          <option value="small_scale">small_scale</option>
          <option value="hs300">沪深300</option>
          <option value="csi500">中证500</option>
        </select>
        <input
          type="number"
          min={2}
          max={20}
          value={settings.n_groups}
          onChange={(e) => setSettings((s) => ({ ...s, n_groups: Number(e.target.value) }))}
          className="rounded-lg border border-gray-200 px-2 py-1.5 text-xs"
          title="分组数"
        />
        <input
          type="number"
          min={1}
          max={60}
          value={settings.holding_period}
          onChange={(e) => setSettings((s) => ({ ...s, holding_period: Number(e.target.value) }))}
          className="rounded-lg border border-gray-200 px-2 py-1.5 text-xs"
          title="持仓周期"
        />
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={isLoading || factors.filter((f) => f.expression.trim()).length < 2}
        className="w-full flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        {isLoading ? "组合回测中..." : "开始组合回测"}
      </button>

      {/* Attribution analysis — show when at least 2 valid factors */}
      {factors.filter((f) => f.expression.trim()).length >= 2 && (
        <AttributionChart
          factors={factors.filter((f) => f.expression.trim()).map((f, i) => ({
            ...f,
            label: f.label || `Factor_${i + 1}`,
          }))}
          universe={settings.universe}
          startDate={settings.start_date}
          endDate={settings.end_date}
          nGroups={settings.n_groups}
          holdingPeriod={settings.holding_period}
        />
      )}
    </div>
  );
}
