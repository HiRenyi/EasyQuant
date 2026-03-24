import { useCallback, useState, useEffect } from "react";
import type { Task } from "./types/backtest";
import { useBacktest } from "./hooks/useBacktest";
import { useTaskHistory } from "./hooks/useTaskHistory";
import { useSession } from "./hooks/useSession";
import { useAuth } from "./contexts/AuthContext";
import { useColorMode } from "./contexts/ColorModeContext";
import Header from "./components/Header";
import BacktestForm from "./components/BacktestForm";
import ProgressTracker from "./components/ProgressTracker";
import ResultsDashboard from "./components/ResultsDashboard";
import SessionSidebar from "./components/SessionSidebar";
import IterationPanel from "./components/IterationPanel";
import FeedbackButton from "./components/FeedbackButton";
import SatisfactionRating from "./components/SatisfactionRating";
import FactorLibrary from "./components/FactorLibrary";
import FactorWall from "./components/FactorWall";
import TemplateGallery from "./components/TemplateGallery";
import CompositeBuilder from "./components/CompositeBuilder";
import FactorComparison from "./components/FactorComparison";
import PaperTrading from "./components/PaperTrading";
import DailySummary from "./components/DailySummary";
import { Star, MessageSquare, FlaskConical, BookOpen, Layers, BarChart3, Trophy, LineChart, Newspaper } from "lucide-react";
import { saveFactor, fetchFactors } from "./api/factorLibrary";
import { submitCompositeBacktest } from "./api/composite";
import type { CompositeBacktestPayload } from "./api/composite";

type MainTab = "backtest" | "daily" | "templates" | "leaderboard" | "composite" | "comparison" | "paper";

const TABS: { id: MainTab; label: string; icon: typeof FlaskConical; color: string }[] = [
  { id: "backtest", label: "单因子回测", icon: FlaskConical, color: "blue" },
  { id: "daily", label: "盘后日报", icon: Newspaper, color: "rose" },
  { id: "templates", label: "因子模板库", icon: BookOpen, color: "indigo" },
  { id: "leaderboard", label: "因子榜", icon: Trophy, color: "amber" },
  { id: "composite", label: "多因子组合", icon: Layers, color: "purple" },
  { id: "comparison", label: "因子对比", icon: BarChart3, color: "emerald" },
  { id: "paper", label: "模拟盘", icon: LineChart, color: "teal" },
];

export default function App() {
  const { isGuest } = useAuth();
  const { isDark } = useColorMode();
  const [activeTab, setActiveTab] = useState<MainTab>("backtest");
  const [sidebarTab, setSidebarTab] = useState<"sessions" | "factors">("sessions");
  const [factorLibKey, setFactorLibKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [savedExpressions, setSavedExpressions] = useState<Set<string>>(new Set());

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

  const handleUseTemplate = useCallback(
    (expression: string, params?: { universe: string; holding_period: number; n_groups: number }) => {
      setActiveTab("backtest");
      submit({
        prompt: expression,
        ...(params ? {
          universe: params.universe,
          holding_period: params.holding_period,
          n_groups: params.n_groups,
        } : {}),
      });
    },
    [submit]
  );

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
      <div className={`border-b ${isDark ? "border-gray-800 bg-gray-900" : "border-gray-200 bg-white"}`}>
        <div className="mx-auto max-w-7xl px-6">
          <nav className="flex items-center gap-1 -mb-px">
            {/* Tab buttons */}
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? isDark
                        ? "border-blue-400 text-blue-400"
                        : `border-${tab.color}-600 text-${tab.color}-600`
                      : isDark
                        ? "border-transparent text-gray-500 hover:text-gray-300 hover:border-gray-700"
                        : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                  }`}
                  style={isActive && !isDark ? {
                    borderBottomColor: tab.color === "blue" ? "#2563eb"
                      : tab.color === "rose" ? "#e11d48"
                      : tab.color === "indigo" ? "#4f46e5"
                      : tab.color === "amber" ? "#d97706"
                      : tab.color === "purple" ? "#9333ea"
                      : tab.color === "teal" ? "#0d9488"
                      : "#059669",
                    color: tab.color === "blue" ? "#2563eb"
                      : tab.color === "rose" ? "#e11d48"
                      : tab.color === "indigo" ? "#4f46e5"
                      : tab.color === "amber" ? "#d97706"
                      : tab.color === "purple" ? "#9333ea"
                      : tab.color === "teal" ? "#0d9488"
                      : "#059669",
                  } : isActive && isDark ? {
                    borderBottomColor: "#60a5fa",
                    color: "#93bbfd",
                  } : undefined}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-6 flex gap-6">
        {/* Main content area — changes per tab */}
        <main className={`min-w-0 space-y-4 ${activeTab === "backtest" ? "flex-1" : "w-full"}`}>
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
                  <button
                    onClick={() => window.dispatchEvent(new CustomEvent("open-feedback", {
                      detail: {
                        task_id: activeTask.task_id,
                        prefill: `回测失败: ${typeof activeTask.error === "string" ? activeTask.error : JSON.stringify(activeTask.error) || "未知错误"}${activeTask.expression ? `\n表达式: ${activeTask.expression}` : ""}`,
                      },
                    }))}
                    className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 bg-red-100 hover:bg-red-200 rounded-lg transition-colors"
                  >
                    一键反馈此问题
                  </button>
                </div>
              )}

              {showResults && activeTask.result && (
                <>
                <SatisfactionRating taskId={activeTask.task_id} expression={activeTask.result.params.expression} />
                <ResultsDashboard
                  result={activeTask.result}
                  onSaveFactor={isGuest ? undefined : handleSaveFactor}
                  isSaving={saving}
                  isSaved={savedExpressions.has(activeTask.result.params.expression)}
                  showSubmitToWall={!isGuest}
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
                </>
              )}
            </>
          )}

          {activeTab === "daily" && (
            <DailySummary />
          )}

          {activeTab === "templates" && (
            <TemplateGallery onUseTemplate={handleUseTemplate} />
          )}

          {activeTab === "leaderboard" && (
            <FactorWall onTryFactor={(expr) => { setActiveTab("backtest"); handleSubmit({ prompt: expr }); }} />
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

        {/* Sidebar — only visible on backtest tab for logged-in users */}
        {activeTab === "backtest" && !isGuest && (
          <aside className="w-72 shrink-0 hidden lg:block">
            <div className="sticky top-6 max-h-[calc(100vh-3rem)] flex flex-col">
              <div className="flex gap-1 mb-3 shrink-0">
                <button
                  onClick={() => setSidebarTab("sessions")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    sidebarTab === "sessions" ? "bg-blue-50 text-blue-700" : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  会话
                </button>
                <button
                  onClick={() => setSidebarTab("factors")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    sidebarTab === "factors" ? "bg-amber-50 text-amber-700" : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  <Star className="h-3.5 w-3.5" />
                  因子库
                </button>
              </div>
              <div className="overflow-y-auto min-h-0">
                {sidebarTab === "sessions" ? (
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
                ) : (
                  <FactorLibrary key={factorLibKey} />
                )}
              </div>
            </div>
          </aside>
        )}
      </div>
      <FeedbackButton />
    </div>
  );
}
