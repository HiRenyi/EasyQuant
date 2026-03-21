import { useState, useCallback } from "react";
import { Plus, Trash2, Play, Loader2, Shuffle } from "lucide-react";
import type { FactorItem, CompositeBacktestPayload } from "../api/composite";
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

      <button
        onClick={addFactor}
        disabled={factors.length >= 10}
        className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 disabled:opacity-50"
      >
        <Plus className="h-3.5 w-3.5" />
        添加因子 ({factors.length}/10)
      </button>

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
