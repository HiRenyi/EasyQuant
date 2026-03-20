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
    <div className="min-h-screen grid-pattern noise-overlay">
      {/* Ambient glow effects */}
      <div className="fixed top-0 left-1/4 w-96 h-96 rounded-full opacity-[0.03] pointer-events-none" style={{ background: 'radial-gradient(circle, var(--accent-green) 0%, transparent 70%)' }} />
      <div className="fixed bottom-0 right-1/4 w-96 h-96 rounded-full opacity-[0.02] pointer-events-none" style={{ background: 'radial-gradient(circle, var(--accent-cyan) 0%, transparent 70%)' }} />

      <Header />

      <div className="mx-auto max-w-7xl px-6 py-6 flex gap-6 relative">
        <main className="flex-1 min-w-0 space-y-5">
          <div className="animate-slide-up">
            <BacktestForm onSubmit={handleSubmit} isLoading={isLoading} />
          </div>

          {showProgress && (
            <div className="animate-slide-up">
              <ProgressTracker status={activeTask.status} expression={activeTask.expression} />
            </div>
          )}

          {showError && activeTask && (
            <div className="animate-slide-up glass-card p-5" style={{ borderColor: 'rgba(255, 56, 96, 0.3)' }}>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-[var(--accent-red)] animate-pulse" />
                <p className="text-sm font-semibold text-[var(--accent-red)]">回测失败</p>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">{activeTask.error}</p>
              {activeTask.expression && (
                <div className="mt-3 px-3 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)]">
                  <code className="text-xs text-[var(--accent-red)] font-mono opacity-80">
                    {activeTask.expression}
                  </code>
                </div>
              )}
            </div>
          )}

          {showResults && activeTask.result && (
            <div className="animate-slide-up">
              <ResultsDashboard result={activeTask.result} />
            </div>
          )}
        </main>

        <aside className="w-72 shrink-0 hidden lg:block">
          <div className="sticky top-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-4 rounded-full bg-[var(--accent-cyan)]" />
              <h2 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-[0.15em]">
                历史任务
              </h2>
            </div>
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
