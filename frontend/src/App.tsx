import { useCallback } from "react";
import type { Task } from "./types/backtest";
import { useBacktest } from "./hooks/useBacktest";
import { useTaskHistory } from "./hooks/useTaskHistory";
import { useSession } from "./hooks/useSession";
import Header from "./components/Header";
import BacktestForm from "./components/BacktestForm";
import ProgressTracker from "./components/ProgressTracker";
import ResultsDashboard from "./components/ResultsDashboard";
import SessionSidebar from "./components/SessionSidebar";
import IterationPanel from "./components/IterationPanel";
import FeedbackButton from "./components/FeedbackButton";

export default function App() {
  const {
    sessions,
    activeSessionId,
    createSession,
    switchSession,
    renameSession,
    deleteSession,
    refreshSessions,
  } = useSession();

  const { tasks, addTask } = useTaskHistory(activeSessionId);

  const onComplete = useCallback(
    (task: Task) => {
      addTask(task);
      refreshSessions(); // pick up auto-named session
    },
    [addTask, refreshSessions]
  );

  const {
    activeTask,
    isLoading,
    submit,
    setActiveTask,
    iterationTask,
    isIterating,
    iterate,
    handleSelectCandidate,
  } = useBacktest(onComplete, activeSessionId);

  const handleSubmit = useCallback(
    (req: Parameters<typeof submit>[0]) => {
      submit(req);
    },
    [submit]
  );

  const handleSwitchSession = useCallback(
    (id: string) => {
      switchSession(id);
      setActiveTask(null);
    },
    [switchSession, setActiveTask]
  );

  const handleCreateSession = useCallback(async () => {
    await createSession();
    setActiveTask(null);
  }, [createSession, setActiveTask]);

  const showProgress =
    activeTask &&
    activeTask.status !== "pending" &&
    activeTask.status !== "completed" &&
    activeTask.status !== "failed";
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
            <ResultsDashboard
              result={activeTask.result}
              iterationSlot={
                <IterationPanel
                  parentTaskId={activeTask.task_id}
                  iterationTask={iterationTask}
                  isIterating={isIterating}
                  onIterate={iterate}
                  onSelectCandidate={handleSelectCandidate}
                />
              }
            />
          )}
        </main>

        <aside className="w-72 shrink-0 hidden lg:block">
          <div className="sticky top-6 max-h-[calc(100vh-3rem)] flex flex-col">
            <h2 className="text-sm font-medium text-gray-500 mb-3 shrink-0">会话</h2>
            <div className="overflow-y-auto min-h-0">
              <SessionSidebar
              sessions={sessions}
              activeSessionId={activeSessionId}
              tasks={tasks}
              activeTaskId={activeTask?.task_id}
              onCreateSession={handleCreateSession}
              onSwitchSession={handleSwitchSession}
              onRenameSession={renameSession}
              onDeleteSession={deleteSession}
              onSelectTask={(task) => setActiveTask(task)}
            />
            </div>
          </div>
        </aside>
      </div>
      <FeedbackButton />
    </div>
  );
}
