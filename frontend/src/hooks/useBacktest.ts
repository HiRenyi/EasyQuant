import { useState, useRef, useCallback } from "react";
import type { Task, BacktestRequest } from "../types/backtest";
import { submitBacktest, streamTask } from "../api/client";

export function useBacktest(onComplete?: (task: Task) => void) {
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const closeRef = useRef<(() => void) | null>(null);

  const stopStream = useCallback(() => {
    closeRef.current?.();
    closeRef.current = null;
  }, []);

  const submit = useCallback(
    async (req: BacktestRequest) => {
      stopStream();
      setIsLoading(true);
      try {
        const { task_id } = await submitBacktest(req);
        const initial: Task = { task_id, status: "pending", params: req };
        setActiveTask(initial);

        closeRef.current = streamTask(
          task_id,
          (task) => {
            setActiveTask(task);
            if (task.status === "completed" || task.status === "failed") {
              setIsLoading(false);
              onComplete?.(task);
            }
          },
          () => {
            setIsLoading(false);
          },
          () => {
            setIsLoading(false);
          },
        );
      } catch (err) {
        setIsLoading(false);
        setActiveTask({
          task_id: "error",
          status: "failed",
          error: err instanceof Error ? err.message : "Unknown error",
        });
      }
    },
    [stopStream, onComplete]
  );

  return { activeTask, isLoading, submit, setActiveTask };
}
