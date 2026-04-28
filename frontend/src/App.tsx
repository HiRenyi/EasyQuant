import { useCallback, useState, useEffect } from "react";
import type { Task } from "./types/backtest";
import type { StrategyTask } from "./types/strategy";
import { useBacktest } from "./hooks/useBacktest";
import { useTaskHistory } from "./hooks/useTaskHistory";
import { useSession } from "./hooks/useSession";
import { useAuth } from "./contexts/AuthContext";
import { useColorMode } from "./contexts/ColorModeContext";
import Header from "./components/Header";
import BacktestForm from "./components/BacktestForm";
import ProgressTracker from "./components/ProgressTracker";
import ResultsDashboard from "./components/ResultsDashboard";
import IterationPanel from "./components/IterationPanel";
import CompositeBuilder from "./components/CompositeBuilder";
import FactorComparison from "./components/FactorComparison";
import PaperTrading from "./components/PaperTrading";
import StrategyBacktest from "./components/StrategyBacktest";
import ResearchDashboard from "./components/ResearchDashboard";
import TabNavigation, { TABS } from "./components/TabNavigation";
import type { MainTab } from "./components/TabNavigation";
import AppSidebar from "./components/AppSidebar";
import { saveFactor, fetchFactors } from "./api/factorLibrary";
import { submitCompositeBacktest } from "./api/composite";
import type { CompositeBacktestPayload } from "./api/composite";

function getTabFromHash(): MainTab {
  const hash = window.location.hash.replace("#", "");
  const validIds = TABS.map((t) => t.id);
  if (validIds.includes(hash as MainTab)) return hash as MainTab;
  return "dashboard";
}

export default function App() {
  const { isGuest } = useAuth();
  const { isDark } = useColorMode();
  const [activeTab, setActiveTab] = useState<MainTab>(getTabFromHash);
  const [sidebarTab, setSidebarTab] = useState<"sessions" | "factors">("sessions");
  const [factorLibKey, setFactorLibKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [savedExpressions, setSavedExpressions] = useState<Set<string>>(new Set());

  // Sync activeTab with URL hash
  useEffect(() => {
    window.location.hash = activeTab;
  }, [activeTab]);

  useEffect(() => {
    const onHashChange = () => {
      const tab = getTabFromHash();
      setActiveTab(tab);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // Load saved expressions on mount (skip for guests)
  useEffect(() => {
    if (isGuest) return;
    fetchFactors().then((factors) => {
      setSavedExpressions(new Set(factors.map((f) => f.expression)));
    }).catch(() => {});
  }, [factorLibKey, isGuest]);

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

  // Strategy backtest history (separate from factor tasks)
  const { tasks: strategyTasks, addTask: addStrategyTask } = useTaskHistory(activeSessionId, "strategy_backtest");
  const [restoredStrategyTask, setRestoredStrategyTask] = useState<StrategyTask | null>(null);

  const onStrategyComplete = useCallback(
    (task: StrategyTask) => {
      addStrategyTask(task as unknown as Task);
      refreshSessions();
    },
    [addStrategyTask, refreshSessions]
  );

  const onComplete = useCallback(
    (task: Task) => {
      addTask(task);
      refreshSessions();
    },
    [addTask, refreshSessions]
  );

  const {
    activeTask,
    isLoading,
    submit,
    cancel,
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

  const handleCompositeSubmit = useCallback(
    async (payload: CompositeBacktestPayload) => {
      setActiveTab("backtest");
      try {
        const { task_id } = await submitCompositeBacktest({
          ...payload,
          session_id: activeSessionId ?? undefined,
        });
        const { streamTask } = await import("./api/client");
        const initial: Task = { task_id, status: "pending", task_type: "composite" as Task["task_type"] };
        setActiveTask(initial);
        streamTask(
          task_id,
          (task) => {
            setActiveTask(task);
            if (task.status === "completed" || task.status === "failed") {
              onComplete(task);
            }
          },
          () => {},
          () => {},
        );
      } catch (err) {
        alert(err instanceof Error ? err.message : "组合回测失败");
      }
    },
    [activeSessionId, setActiveTask, onComplete]
  );

  const handleSaveFactor = useCallback(async () => {
    if (!activeTask?.result || saving) return;
    const expr = activeTask.result.params.expression;
    if (savedExpressions.has(expr)) return;
    setSaving(true);
    try {
      await saveFactor({
        task_id: activeTask.task_id,
        expression: expr,
        metrics: activeTask.result.metrics as unknown as Record<string, unknown>,
        backtest_summary: activeTask.result.backtest_summary as unknown as Record<string, unknown>,
        params: activeTask.result.params as unknown as Record<string, unknown>,
        report_url: activeTask.result.report_url,
      });
      setSavedExpressions((prev) => new Set(prev).add(expr));
      setFactorLibKey((k) => k + 1);
      setSidebarTab("factors");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "未知错误";
      if (msg.includes("已收藏")) {
        setSavedExpressions((prev) => new Set(prev).add(expr));
      } else {
        alert("收藏失败: " + msg);
      }
    } finally {
      setSaving(false);
    }
  }, [activeTask, saving, savedExpressions]);

  const showProgress =
    activeTask &&
    activeTask.status !== "pending" &&
    activeTask.status !== "completed" &&
    activeTask.status !== "failed";
  const showResults = activeTask?.status === "completed" && activeTask.result;
  const showError = activeTask?.status === "failed";


  return (
    <div className={`min-h-screen ${isDark ? "bg-gray-950" : "bg-[#f9fafb]"}`}>
      <Header />

      {/* Main navigation tabs */}
      <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} isDark={isDark} />

      <div className="mx-auto max-w-7xl px-6 py-6 flex gap-6">
        {/* Main content area — changes per tab */}
        <main className={`min-w-0 space-y-4 ${(activeTab === "backtest" || activeTab === "strategy") ? "flex-1" : "w-full"}`}>
          {activeTab === "dashboard" && (
            <ResearchDashboard />
          )}

          {activeTab === "backtest" && (
            <>
              <BacktestForm onSubmit={handleSubmit} isLoading={isLoading} />

              {showProgress && (
                <ProgressTracker status={activeTask.status} expression={activeTask.expression} onCancel={cancel} />
              )}

              {showError && activeTask && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                  <p className="text-sm font-medium text-red-700">回测失败</p>
                  <p className="mt-1 text-sm text-red-600">{typeof activeTask.error === "string" ? activeTask.error : (activeTask.error && typeof activeTask.error === "object" ? JSON.stringify(activeTask.error) : "未知错误")}</p>
                  {activeTask.expression && (
                    <p className="mt-2 text-xs text-red-500 font-mono">表达式: {activeTask.expression}</p>
                  )}
                </div>
              )}

              {showResults && activeTask.result && (
                <ResultsDashboard
                  result={activeTask.result}
                  onSaveFactor={isGuest ? undefined : handleSaveFactor}
                  isSaving={saving}
                  isSaved={savedExpressions.has(activeTask.result.params.expression)}
                  onGoToPaper={isGuest ? undefined : () => setActiveTab("paper")}
                  iterationSlot={isGuest ? undefined :
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
            </>
          )}

          {activeTab === "strategy" && (
            <StrategyBacktest
              sessionId={activeSessionId}
              onComplete={onStrategyComplete}
              restoredTask={restoredStrategyTask}
              onClearRestored={() => setRestoredStrategyTask(null)}
            />
          )}

          {activeTab === "composite" && (
            <CompositeBuilder
              onSubmit={handleCompositeSubmit}
              isLoading={isLoading}
              savedExpressions={Array.from(savedExpressions)}
            />
          )}

          {activeTab === "comparison" && (
            <FactorComparison savedExpressions={Array.from(savedExpressions)} />
          )}

          {activeTab === "paper" && !isGuest && (
            <PaperTrading />
          )}
        </main>

        {/* Sidebar — visible on backtest and strategy tabs for logged-in users */}
        {(activeTab === "backtest" || activeTab === "strategy") && !isGuest && (
          <AppSidebar
            activeTab={activeTab}
            sidebarTab={sidebarTab}
            onSidebarTabChange={setSidebarTab}
            sessions={sessions}
            activeSessionId={activeSessionId}
            tasks={tasks}
            activeTaskId={activeTask?.task_id}
            onCreateSession={handleCreateSession}
            onSwitchSession={handleSwitchSession}
            onRenameSession={renameSession}
            onDeleteSession={deleteSession}
            onSelectTask={(task) => setActiveTask(task)}
            factorLibKey={factorLibKey}
            strategyTasks={strategyTasks}
            restoredStrategyTaskId={restoredStrategyTask?.task_id}
            onStrategySwitchSession={(id) => { switchSession(id); setRestoredStrategyTask(null); }}
            onSelectStrategyTask={(task) => setRestoredStrategyTask(task as unknown as StrategyTask)}
          />
        )}
      </div>
    </div>
  );
}
