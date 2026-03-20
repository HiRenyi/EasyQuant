import { useState, useCallback } from "react";
import type { Task } from "../types/backtest";

export function useTaskHistory() {
  const [tasks, setTasks] = useState<Task[]>([]);

  const addTask = useCallback((task: Task) => {
    setTasks((prev) => {
      const exists = prev.find((t) => t.task_id === task.task_id);
      if (exists) {
        return prev.map((t) => (t.task_id === task.task_id ? task : t));
      }
      return [task, ...prev];
    });
  }, []);

  return { tasks, addTask };
}
