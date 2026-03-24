import { Check, Loader2, Circle, X } from "lucide-react";
import type { TaskStatus } from "../types/backtest";
import { useColorMode } from "../contexts/ColorModeContext";

const STEPS: { key: TaskStatus; label: string }[] = [
  { key: "generating_expression", label: "生成表达式" },
  { key: "validating", label: "验证" },
  { key: "fetching_data", label: "拉取数据" },
  { key: "fetching_fundamentals", label: "获取财务数据" },
  { key: "backtesting", label: "回测" },
  { key: "analyzing", label: "分析" },
  { key: "generating_report", label: "生成报告" },
  { key: "completed", label: "完成" },
];

const STATUS_ORDER: TaskStatus[] = [
  "pending",
  "generating_expression",
  "validating",
  "fetching_data",
  "fetching_fundamentals",
  "backtesting",
  "analyzing",
  "generating_report",
  "completed",
];

interface Props {
  status: TaskStatus;
  expression?: string;
  onCancel?: () => void;
}

export default function ProgressTracker({ status, expression, onCancel }: Props) {
  const { isDark } = useColorMode();
  const currentIdx = STATUS_ORDER.indexOf(status);
  const isFailed = status === "failed";
  const isCancelled = status === "cancelled";
  const isRunning = !isFailed && !isCancelled && status !== "completed";

  return (
    <div className={`rounded-xl border ${isDark ? "border-gray-700" : "border-gray-200"} ${isDark ? "bg-gray-900" : "bg-white"} p-5`}>
      <div className="flex items-center gap-1">
        {STEPS.map((step, i) => {
          const stepIdx = STATUS_ORDER.indexOf(step.key);
          const isDone = !isFailed && !isCancelled && currentIdx > stepIdx;
          const isActive = !isFailed && !isCancelled && currentIdx === stepIdx;
          const isFailedStep = isFailed && currentIdx === stepIdx;

          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                    isDone
                      ? isDark ? "bg-emerald-500/10 text-emerald-400" : "bg-emerald-100 text-emerald-600"
                      : isActive
                        ? isDark ? "bg-amber-500/10 text-amber-400" : "bg-blue-100 text-blue-600"
                        : isFailedStep
                          ? isDark ? "bg-red-500/10 text-red-400" : "bg-red-100 text-red-600"
                          : isDark ? "bg-gray-800 text-gray-500" : "bg-gray-100 text-gray-400"
                  }`}
                >
                  {isDone ? (
                    <Check className="h-4 w-4" />
                  ) : isActive ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Circle className="h-3 w-3" />
                  )}
                </div>
                <span className={`text-xs whitespace-nowrap ${isActive ? (isDark ? "text-amber-400 font-medium" : "text-blue-600 font-medium") : isDone ? (isDark ? "text-emerald-400" : "text-emerald-600") : (isDark ? "text-gray-500" : "text-gray-400")}`}>
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-px mx-2 mt-[-18px] ${isDone ? (isDark ? "bg-emerald-500/30" : "bg-emerald-300") : (isDark ? "bg-gray-700" : "bg-gray-200")}`} />
              )}
            </div>
          );
        })}
      </div>
      {expression && (
        <div className="mt-4 flex items-start justify-between gap-3">
          <div className={`flex-1 px-3 py-2 rounded-lg ${isDark ? "bg-gray-800" : "bg-gray-50"} border ${isDark ? "border-gray-700" : "border-gray-100"}`}>
            <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"} mb-1`}>生成的因子表达式</p>
            <code className={`text-sm ${isDark ? "text-amber-400" : "text-blue-700"} font-mono`}>{expression}</code>
          </div>
          {isRunning && onCancel && (
            <button
              onClick={onCancel}
              className={`shrink-0 flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-500"} ${isDark ? "bg-gray-800" : "bg-gray-50"} border ${isDark ? "border-gray-700" : "border-gray-200"} hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors`}
            >
              <X className="h-3.5 w-3.5" />
              取消
            </button>
          )}
        </div>
      )}
      {!expression && isRunning && onCancel && (
        <div className="mt-4 flex justify-end">
          <button
            onClick={onCancel}
            className={`flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-500"} ${isDark ? "bg-gray-800" : "bg-gray-50"} border ${isDark ? "border-gray-700" : "border-gray-200"} hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors`}
          >
            <X className="h-3.5 w-3.5" />
            取消
          </button>
        </div>
      )}
      {isFailed && (
        <div className={`mt-4 px-3 py-2 rounded-lg ${isDark ? "bg-red-500/10" : "bg-red-50"} border ${isDark ? "border-red-500/20" : "border-red-100"}`}>
          <p className={`text-sm ${isDark ? "text-red-400" : "text-red-600"}`}>任务失败</p>
        </div>
      )}
      {isCancelled && (
        <div className={`mt-4 px-3 py-2 rounded-lg ${isDark ? "bg-orange-500/10" : "bg-orange-50"} border ${isDark ? "border-orange-500/20" : "border-orange-100"}`}>
          <p className={`text-sm ${isDark ? "text-orange-400" : "text-orange-600"}`}>已取消回测</p>
        </div>
      )}
    </div>
  );
}
