import { useCallback } from "react";
import type { Task } from "./types/backtest";
import { useBacktest } from "./hooks/useBacktest";
import { useTaskHistory } from "./hooks/useTaskHistory";
import Header from "./components/Header";
import BacktestForm from "./components/BacktestForm";
import ProgressTracker from "./components/ProgressTracker";
import ResultsDashboard from "./components/ResultsDashboard";
import TaskHistory from "./components/TaskHistory";

export default function App() {
  const { tasks, addTask } = useTaskHistory();

  const onComplete = useCallback(
    (task: Task) => addTask(task),
    [addTask]
  );

  const { activeTask, isLoading, submit, setActiveTask } = useBacktest(onComplete);

  const handleSubmit = useCallback(
    (req: Parameters<typeof submit>[0]) => {
      submit(req);
    },
    [submit]
  );

  const showProgress =
    activeTask && activeTask.status !== "pending" && activeTask.status !== "completed";
  const showResults = activeTask?.status === "completed" && activeTask.result;
  const showError = activeTask?.status === "failed";

  return (
    <div className="min-h-screen bg-[#f9fafb]">
      <Header />
      <div className="mx-auto max-w-7xl px-6 py-6 flex gap-6">
        <main className="flex-1 min-w-0 space-y-4">
          <BacktestForm onSubmit={handleSubmit} isLoading={isLoading} />

          {showProgress && (
            <ProgressTracker status={activeTask.status} expression={activeTask.expression} />
          )}

          {showError && activeTask && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <p className="text-sm font-medium text-red-700">回测失败</p>
              <p className="mt-1 text-sm text-red-600">{activeTask.error}</p>
              {activeTask.expression && (
                <p className="mt-2 text-xs text-red-500 font-mono">表达式: {activeTask.expression}</p>
              )}
            </div>
          )}

          {showResults && activeTask.result && (
            <ResultsDashboard result={activeTask.result} />
          )}
        </main>

        <aside className="w-72 shrink-0 hidden lg:block">
          <div className="sticky top-6">
            <h2 className="text-sm font-medium text-gray-500 mb-3">历史任务</h2>
            <TaskHistory
              tasks={tasks}
              activeTaskId={activeTask?.task_id}
              onSelect={(task) => setActiveTask(task)}
            />
          </div>
        </aside>
      </div>
    </div>
  );
}
