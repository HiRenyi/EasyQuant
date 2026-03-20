import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import type { Task } from "../types/backtest";

interface Props {
  task: Task;
  isActive: boolean;
  onClick: () => void;
}

export default function TaskHistoryItem({ task, isActive, onClick }: Props) {
  const prompt = task.params?.prompt ?? task.result?.llm?.prompt ?? "—";
  const expression = task.expression ?? task.result?.params?.expression;

  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-xl p-3 transition-all duration-200 border"
      style={{
        background: isActive ? 'rgba(0, 255, 136, 0.04)' : 'var(--bg-glass)',
        borderColor: isActive ? 'rgba(0, 255, 136, 0.25)' : 'var(--border-subtle)',
        backdropFilter: 'blur(12px)',
        boxShadow: isActive ? '0 0 16px rgba(0, 255, 136, 0.06)' : 'none',
      }}
    >
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5">
          {task.status === "completed" ? (
            <CheckCircle2 className="h-4 w-4 text-[var(--accent-green)]" />
          ) : task.status === "failed" ? (
            <XCircle className="h-4 w-4 text-[var(--accent-red)]" />
          ) : (
            <Loader2 className="h-4 w-4 text-[var(--accent-cyan)] animate-spin" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs text-[var(--text-primary)] truncate leading-relaxed">
            {prompt}
          </p>
          {expression && (
            <p className="text-[10px] text-[var(--accent-green)] font-mono truncate mt-1 opacity-60">
              {expression}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}
