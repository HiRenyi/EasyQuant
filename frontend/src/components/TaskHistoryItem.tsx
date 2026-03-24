import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import type { Task } from "../types/backtest";
import { useColorMode } from "../contexts/ColorModeContext";

interface Props {
  task: Task;
  isActive: boolean;
  onClick: () => void;
}

export default function TaskHistoryItem({ task, isActive, onClick }: Props) {
  const { isDark } = useColorMode();
  const prompt = task.params?.prompt ?? task.result?.llm?.prompt ?? "—";
  const expression = task.expression ?? task.result?.params?.expression;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-xl border p-3 transition-colors ${
        isActive
          ? isDark ? "border-amber-500/50 bg-amber-500/10" : "border-blue-300 bg-blue-50/50"
          : isDark ? "border-gray-700 bg-gray-900 hover:border-gray-600" : "border-gray-200 bg-white hover:border-gray-300"
      }`}
    >
      <div className="flex items-start gap-2">
        <div className="mt-0.5">
          {task.status === "completed" ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          ) : task.status === "failed" ? (
            <XCircle className="h-4 w-4 text-red-500" />
          ) : (
            <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className={`text-sm ${isDark ? "text-gray-200" : "text-gray-800"} truncate`}>{prompt}</p>
          {expression && (
            <p className="text-xs text-gray-400 font-mono truncate mt-0.5">{expression}</p>
          )}
        </div>
      </div>
    </button>
  );
}
