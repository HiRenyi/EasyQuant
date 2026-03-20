import type { Task } from "../types/backtest";
import TaskHistoryItem from "./TaskHistoryItem";

interface Props {
  tasks: Task[];
  activeTaskId?: string;
  onSelect: (task: Task) => void;
}

export default function TaskHistory({ tasks, activeTaskId, onSelect }: Props) {
  if (tasks.length === 0) {
    return (
      <div className="glass-card px-4 py-8 text-center">
        <div className="text-[var(--text-muted)] text-2xl mb-2">
          { /* terminal cursor blink */ }
          <span className="font-mono text-sm text-[var(--text-muted)]">
            <span className="opacity-50">$</span> <span className="animate-pulse">_</span>
          </span>
        </div>
        <p className="text-xs text-[var(--text-muted)]">暂无历史任务</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {tasks.map((task, i) => (
        <div key={task.task_id} className="animate-slide-up" style={{ animationDelay: `${i * 50}ms` }}>
          <TaskHistoryItem
            task={task}
            isActive={task.task_id === activeTaskId}
            onClick={() => onSelect(task)}
          />
        </div>
      ))}
    </div>
  );
}
