import { useState, useRef, useCallback } from "react";
import type { StrategyTask, StrategyBacktestRequest } from "../types/strategy";
import { submitStrategyBacktest } from "../api/strategyBacktest";
import { streamTask } from "../api/client";

export function useStrategyBacktest(
  onComplete?: (task: StrategyTask) => void,
  sessionId?: string | null,
) {
  const [activeTask, setActiveTask] = useState<StrategyTask | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const closeRef = useRef<(() => void) | null>(null);

  const stopStream = useCallback(() => {
    closeRef.current?.();
    closeRef.current = null;
  }, []);

  const submit = useCallback(
    async (req: StrategyBacktestRequest) => {
      stopStream();
      setIsLoading(true);
      try {
        const payload = sessionId ? { ...req, session_id: sessionId } : req;
        const { task_id } = await submitStrategyBacktest(payload);
        const initial: StrategyTask = {
          task_id,
          status: "pending",
          task_type: "strategy_backtest",
          params: req,
        };
        setActiveTask(initial);

        closeRef.current = streamTask(
          task_id,
          (task) => {
            // Map the generic Task to StrategyTask
            const sTask: StrategyTask = {
              task_id: task.task_id,
              status: task.status as StrategyTask["status"],
              task_type: "strategy_backtest",
              strategy_code: (task as any).strategy_code,
              strategy_code_encrypted: (task as any).strategy_code_encrypted,
              validation: (task as any).validation,
              error: task.error,
              result: task.result as any,
              params: req,
            };
            setActiveTask(sTask);
            if (task.status === "completed" || task.status === "failed" || task.status === "cancelled") {
              setIsLoading(false);
              onComplete?.(sTask);
            }
          },
          () => { setIsLoading(false); },
          () => { setIsLoading(false); },
        );
      } catch (err) {
        setIsLoading(false);
        setActiveTask({
          task_id: "error",
          status: "failed",
          task_type: "strategy_backtest",
          error: err instanceof Error ? err.message : "提交失败",
        });
      }
    },
    [stopStream, onComplete, sessionId],
  );

  const cancel = useCallback(async () => {
    if (!activeTask) return;
    stopStream();
    try {
      const { cancelTask } = await import("../api/client");
      await cancelTask(activeTask.task_id);
    } catch { /* ignore */ }
    setIsLoading(false);
  }, [activeTask, stopStream]);

  return { activeTask, setActiveTask, isLoading, submit, cancel };
}
