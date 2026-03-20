import { Check, Loader2 } from "lucide-react";
import type { TaskStatus } from "../types/backtest";

const STEPS: { key: TaskStatus; label: string; code: string }[] = [
  { key: "generating_expression", label: "生成表达式", code: "EXPR" },
  { key: "validating", label: "验证", code: "VALI" },
  { key: "fetching_data", label: "拉取数据", code: "DATA" },
  { key: "backtesting", label: "回测", code: "BTST" },
  { key: "generating_report", label: "生成报告", code: "REPT" },
  { key: "completed", label: "完成", code: "DONE" },
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
    <div className="glass-card p-5">
      {/* Pipeline visualization */}
      <div className="flex items-center gap-1">
        {STEPS.map((step, i) => {
          const stepIdx = STATUS_ORDER.indexOf(step.key);
          const isDone = !isFailed && currentIdx > stepIdx;
          const isActive = !isFailed && currentIdx === stepIdx;
          const isFailedStep = isFailed && currentIdx === stepIdx;

          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-2">
                {/* Step indicator */}
                <div
                  className="relative h-9 w-9 rounded-lg flex items-center justify-center text-[10px] font-bold font-mono tracking-wider transition-all duration-300"
                  style={{
                    background: isDone
                      ? 'rgba(0, 255, 136, 0.12)'
                      : isActive
                        ? 'rgba(0, 212, 255, 0.12)'
                        : isFailedStep
                          ? 'rgba(255, 56, 96, 0.12)'
                          : 'var(--bg-elevated)',
                    border: `1px solid ${
                      isDone
                        ? 'rgba(0, 255, 136, 0.3)'
                        : isActive
                          ? 'rgba(0, 212, 255, 0.3)'
                          : isFailedStep
                            ? 'rgba(255, 56, 96, 0.3)'
                            : 'var(--border-subtle)'
                    }`,
                    boxShadow: isActive
                      ? '0 0 16px rgba(0, 212, 255, 0.2)'
                      : isDone
                        ? '0 0 12px rgba(0, 255, 136, 0.1)'
                        : 'none',
                    color: isDone
                      ? 'var(--accent-green)'
                      : isActive
                        ? 'var(--accent-cyan)'
                        : isFailedStep
                          ? 'var(--accent-red)'
                          : 'var(--text-muted)',
                  }}
                >
                  {isDone ? (
                    <Check className="h-4 w-4" />
                  ) : isActive ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    step.code
                  )}
                  {isActive && (
                    <div className="absolute inset-0 rounded-lg animate-ping opacity-20" style={{
                      border: '1px solid var(--accent-cyan)',
                    }} />
                  )}
                </div>

                {/* Step label */}
                <span
                  className="text-[10px] whitespace-nowrap font-medium tracking-wide"
                  style={{
                    color: isActive
                      ? 'var(--accent-cyan)'
                      : isDone
                        ? 'var(--accent-green)'
                        : 'var(--text-muted)',
                  }}
                >
                  {step.label}
                </span>
              </div>

              {/* Connector line */}
              {i < STEPS.length - 1 && (
                <div className="flex-1 mx-2 mt-[-18px]">
                  <div
                    className="h-px transition-all duration-500"
                    style={{
                      background: isDone
                        ? 'linear-gradient(90deg, var(--accent-green), rgba(0, 255, 136, 0.3))'
                        : 'var(--border-subtle)',
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Expression display */}
      {expression && (
        <div className="mt-5 px-4 py-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-subtle)]">
          <div className="flex items-center gap-2 mb-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-cyan)]" />
            <p className="text-[10px] text-[var(--text-muted)] font-mono uppercase tracking-wider">
              Generated Expression
            </p>
          </div>
          <code className="text-sm text-[var(--accent-green)] font-mono font-medium">
            {expression}
          </code>
        </div>
      )}

      {isFailed && (
        <div className="mt-5 px-4 py-3 rounded-lg bg-[rgba(255,56,96,0.05)] border border-[rgba(255,56,96,0.2)]">
          <p className="text-sm text-[var(--accent-red)] font-medium">Pipeline Failed</p>
        </div>
      )}
    </div>
  );
}
