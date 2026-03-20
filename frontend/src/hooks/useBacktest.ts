import { useState, useRef, useCallback } from "react";
import type { Task, BacktestRequest } from "../types/backtest";
import { submitBacktest, streamTask, submitIteration, selectCandidate } from "../api/client";

export function useBacktest(onComplete?: (task: Task) => void, sessionId?: string | null) {
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [iterationTask, setIterationTask] = useState<Task | null>(null);
  const [isIterating, setIsIterating] = useState(false);
  const closeRef = useRef<(() => void) | null>(null);

  const stopStream = useCallback(() => {
    closeRef.current?.();
    closeRef.current = null;
  }, []);

  const submit = useCallback(
    async (req: BacktestRequest) => {
      stopStream();
      setIsLoading(true);
      setIterationTask(null);
      setIsIterating(false);
      try {
        const { task_id } = await submitBacktest(req, sessionId ?? undefined);
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
    [stopStream, onComplete, sessionId]
  );

  const iterate = useCallback(
    async (taskId: string, nCandidates = 5) => {
      stopStream();
      setIsIterating(true);
      setIterationTask(null);
      try {
        const { task_id } = await submitIteration(taskId, nCandidates);
        const initial: Task = {
          task_id,
          status: "pending",
          task_type: "iteration",
          parent_task_id: taskId,
          candidates: [],
          candidates_done: 0,
          candidates_total: nCandidates,
        };
        setIterationTask(initial);

        closeRef.current = streamTask(
          task_id,
          (task) => {
            setIterationTask(task);
            if (task.status === "iteration_completed" || task.status === "failed") {
              setIsIterating(false);
            }
          },
          () => {
            setIsIterating(false);
          },
          () => {
            setIsIterating(false);
          },
        );
      } catch (err) {
        setIsIterating(false);
        setIterationTask({
          task_id: "error",
          status: "failed",
          error: err instanceof Error ? err.message : "Unknown error",
        });
      }
    },
    [stopStream]
  );

  const handleSelectCandidate = useCallback(
    async (iterTaskId: string, index: number) => {
      try {
        const result = await selectCandidate(iterTaskId, index);
        // Update active task with selected candidate's data
        if (result.expression) {
          setActiveTask((prev) => {
            if (!prev || !prev.result) return prev;
            return {
              ...prev,
              expression: result.expression as string,
              result: {
                ...prev.result,
                report_url: result.report_url as string,
                metrics: result.report_metrics as typeof prev.result.metrics,
                backtest_summary: result.backtest_summary as typeof prev.result.backtest_summary,
                params: {
                  ...prev.result.params,
                  expression: result.expression as string,
                },
              },
            };
          });
        }
        // Mark selected in iteration task
        setIterationTask((prev) =>
          prev ? { ...prev, selected_candidate_index: index } : prev
        );
      } catch (err) {
        console.error("Select candidate failed:", err);
      }
    },
    []
  );

  return {
    activeTask,
    isLoading,
    submit,
    setActiveTask,
    iterationTask,
    isIterating,
    iterate,
    handleSelectCandidate,
  };
}
