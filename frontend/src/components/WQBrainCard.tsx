import type { WQBrain } from "../types/backtest";
import { useColorMode } from "../contexts/ColorModeContext";

interface Props {
  wqBrain: WQBrain;
}

function pct(n: number): string {
  return (n * 100).toFixed(2) + "%";
}

export default function WQBrainCard({ wqBrain }: Props) {
  const { isDark } = useColorMode();
  const tests = wqBrain.wq_is_tests;
  const testEntries = Object.values(tests);
  const passCount = testEntries.filter((t) => t.pass).length;
  const totalCount = testEntries.length;
  const allPass = passCount === totalCount;

  const formatValue = (key: string, value: number): string => {
    if (key === "returns" || key === "turnover_range") return pct(value);
    if (key === "weight") return pct(value);
    return value.toFixed(4);
  };

  const formatThreshold = (test: (typeof testEntries)[0], key: string): string => {
    if ("threshold_min" in test && test.threshold_min != null && "threshold_max" in test && test.threshold_max != null) {
      return `[${pct(test.threshold_min)}, ${pct(test.threshold_max)}]`;
    }
    if (key === "returns") return pct(test.threshold ?? 0);
    if (key === "weight") return pct(test.threshold ?? 0);
    return String(test.threshold ?? "");
  };

  return (
    <div className={`rounded-xl border ${isDark ? "border-gray-700" : "border-gray-200"} ${isDark ? "bg-gray-900" : "bg-white"} p-4`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium" style={{ color: isDark ? "#e5e7eb" : "#374151" }}>
            WorldQuant BRAIN 兼容性评估
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            allPass
              ? isDark ? "bg-emerald-500/20 text-emerald-400" : "bg-emerald-50 text-emerald-700"
              : isDark ? "bg-amber-500/20 text-amber-400" : "bg-amber-50 text-amber-700"
          }`}>
            D1 模式
          </span>
        </div>
        <span className={`text-xs font-medium ${
          allPass
            ? isDark ? "text-emerald-400" : "text-emerald-600"
            : isDark ? "text-amber-400" : "text-amber-600"
        }`}>
          通过 {passCount}/{totalCount} 项 IS 测试
        </span>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-3">
        <div className={`rounded-lg p-2.5 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
          <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>WQ Sharpe</p>
          <p className={`text-lg font-semibold ${wqBrain.wq_sharpe >= 1.625 ? (isDark ? "text-emerald-400" : "text-emerald-600") : (isDark ? "text-gray-100" : "text-gray-900")}`}>
            {wqBrain.wq_sharpe.toFixed(2)}
          </p>
        </div>
        <div className={`rounded-lg p-2.5 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
          <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>WQ Fitness</p>
          <p className={`text-lg font-semibold ${wqBrain.wq_fitness >= 1.0 ? (isDark ? "text-emerald-400" : "text-emerald-600") : (isDark ? "text-gray-100" : "text-gray-900")}`}>
            {wqBrain.wq_fitness.toFixed(2)}
          </p>
        </div>
        <div className={`rounded-lg p-2.5 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
          <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>WQ Returns</p>
          <p className={`text-lg font-semibold ${Math.abs(wqBrain.wq_returns) >= 0.063 ? (isDark ? "text-emerald-400" : "text-emerald-600") : (isDark ? "text-gray-100" : "text-gray-900")}`}>
            {pct(wqBrain.wq_returns)}
          </p>
        </div>
        <div className={`rounded-lg p-2.5 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
          <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"}`}>WQ Turnover</p>
          <p className={`text-lg font-semibold ${isDark ? "text-gray-100" : "text-gray-900"}`}>
            {pct(wqBrain.wq_turnover)}
          </p>
        </div>
      </div>

      <div className="space-y-1.5">
        {Object.entries(tests).map(([key, test]) => (
          <div key={key} className={`flex items-center justify-between px-3 py-1.5 rounded-lg text-xs ${isDark ? "bg-gray-800/50" : "bg-gray-50"}`}>
            <div className="flex items-center gap-2">
              <span className={test.pass
                ? isDark ? "text-emerald-400" : "text-emerald-500"
                : isDark ? "text-red-400" : "text-red-500"
              }>
                {test.pass ? "✓" : "✗"}
              </span>
              <span className={isDark ? "text-gray-300" : "text-gray-700"}>{test.label}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className={`font-mono font-medium ${
                test.pass
                  ? isDark ? "text-emerald-400" : "text-emerald-600"
                  : isDark ? "text-red-400" : "text-red-500"
              }`}>
                {formatValue(key, test.value)}
              </span>
              <span className={isDark ? "text-gray-500" : "text-gray-400"}>
                {formatThreshold(test, key)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
