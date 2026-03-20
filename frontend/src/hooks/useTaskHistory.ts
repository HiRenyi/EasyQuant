import { useState, useCallback, useEffect } from "react";
import type { Task } from "../types/backtest";
import { fetchTasks } from "../api/client";

export function useTaskHistory(sessionId: string | null) {
  const [tasks, setTasks] = useState<Task[]>([]);

  // Reload tasks when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setTasks([]);
      return;
    }
    fetchTasks(1, 50, sessionId)
      .then(({ tasks: loaded }) => {
        setTasks(loaded);
      })
      .catch(() => {
        setTasks([]);
      });
  }, [sessionId]);

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
