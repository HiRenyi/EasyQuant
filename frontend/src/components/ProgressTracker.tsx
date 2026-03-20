import { Check, Loader2, Circle } from "lucide-react";
import type { TaskStatus } from "../types/backtest";

const STEPS: { key: TaskStatus; label: string }[] = [
  { key: "generating_expression", label: "生成表达式" },
  { key: "validating", label: "验证" },
  { key: "fetching_data", label: "拉取数据" },
  { key: "backtesting", label: "回测" },
  { key: "generating_report", label: "生成报告" },
  { key: "completed", label: "完成" },
];

const STATUS_ORDER: TaskStatus[] = [
  "pending",
  "generating_expression",
  "validating",
  "fetching_data",
  "backtesting",
  "generating_report",
  "completed",
];

interface Props {
  status: TaskStatus;
  expression?: string;
}

export default function ProgressTracker({ status, expression }: Props) {
  const currentIdx = STATUS_ORDER.indexOf(status);
  const isFailed = status === "failed";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="flex items-center gap-1">
        {STEPS.map((step, i) => {
          const stepIdx = STATUS_ORDER.indexOf(step.key);
          const isDone = !isFailed && currentIdx > stepIdx;
          const isActive = !isFailed && currentIdx === stepIdx;
          const isFailedStep = isFailed && currentIdx === stepIdx;

          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                    isDone
                      ? "bg-emerald-100 text-emerald-600"
                      : isActive
                        ? "bg-blue-100 text-blue-600"
                        : isFailedStep
                          ? "bg-red-100 text-red-600"
                          : "bg-gray-100 text-gray-400"
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
                <span className={`text-xs whitespace-nowrap ${isActive ? "text-blue-600 font-medium" : isDone ? "text-emerald-600" : "text-gray-400"}`}>
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-px mx-2 mt-[-18px] ${isDone ? "bg-emerald-300" : "bg-gray-200"}`} />
              )}
            </div>
          );
        })}
      </div>
      {expression && (
        <div className="mt-4 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100">
          <p className="text-xs text-gray-500 mb-1">生成的因子表达式</p>
          <code className="text-sm text-blue-700 font-mono">{expression}</code>
        </div>
      )}
      {isFailed && (
        <div className="mt-4 px-3 py-2 rounded-lg bg-red-50 border border-red-100">
          <p className="text-sm text-red-600">任务失败</p>
        </div>
      )}
    </div>
  );
}
