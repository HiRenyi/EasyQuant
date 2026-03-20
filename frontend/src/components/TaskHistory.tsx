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
      <div className="text-center py-8 text-sm text-gray-400">
        暂无历史任务
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {tasks.map((task) => (
        <TaskHistoryItem
          key={task.task_id}
          task={task}
          isActive={task.task_id === activeTaskId}
          onClick={() => onSelect(task)}
        />
      ))}
    </div>
  );
}
