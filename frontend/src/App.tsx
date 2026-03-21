import { useCallback, useState, useEffect } from "react";
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
import FactorLibrary from "./components/FactorLibrary";
import TemplateGallery from "./components/TemplateGallery";
import CompositeBuilder from "./components/CompositeBuilder";
import FactorComparison from "./components/FactorComparison";
import { Star, MessageSquare, BookOpen, Layers, BarChart3, ChevronDown, ChevronUp } from "lucide-react";
import { saveFactor, fetchFactors } from "./api/factorLibrary";
import { submitCompositeBacktest } from "./api/composite";
import type { CompositeBacktestPayload } from "./api/composite";

export default function App() {
  const [sidebarTab, setSidebarTab] = useState<"sessions" | "factors">("sessions");
  const [factorLibKey, setFactorLibKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [savedExpressions, setSavedExpressions] = useState<Set<string>>(new Set());
  const [showTemplates, setShowTemplates] = useState(false);
  const [showComposite, setShowComposite] = useState(false);
  const [showComparison, setShowComparison] = useState(false);

  // Load saved expressions on mount
  useEffect(() => {
    fetchFactors().then((factors) => {
      setSavedExpressions(new Set(factors.map((f) => f.expression)));
    }).catch(() => {});
  }, [factorLibKey]);

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

  const handleUseTemplate = useCallback(
    (expression: string, params?: { universe: string; holding_period: number; n_groups: number }) => {
      setShowTemplates(false);
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
      setShowComposite(false);
      try {
        const { task_id } = await submitCompositeBacktest({
          ...payload,
          session_id: activeSessionId ?? undefined,
        });
        // Use the same SSE stream mechanism
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
    <div className="min-h-screen bg-[#f9fafb]">
      <Header />
      <div className="mx-auto max-w-7xl px-6 py-6 flex gap-6">
        <main className="flex-1 min-w-0 space-y-4">
          <BacktestForm onSubmit={handleSubmit} isLoading={isLoading} />

          {/* Template Gallery */}
          <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
            <button
              type="button"
              onClick={() => setShowTemplates(!showTemplates)}
              className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <span className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-blue-500" />
                策略模板库
                <span className="text-xs text-gray-400 font-normal">18个经典策略一键回测</span>
              </span>
              {showTemplates ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            {showTemplates && (
              <div className="px-4 pb-4">
                <TemplateGallery onUseTemplate={handleUseTemplate} />
              </div>
            )}
          </div>

          {/* Composite Builder */}
          <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
            <button
              type="button"
              onClick={() => setShowComposite(!showComposite)}
              className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <span className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-purple-500" />
                多因子组合
                <span className="text-xs text-gray-400 font-normal">组合多个因子一键回测</span>
              </span>
              {showComposite ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            {showComposite && (
              <div className="px-4 pb-4">
                <CompositeBuilder
                  onSubmit={handleCompositeSubmit}
                  isLoading={isLoading}
                  savedExpressions={Array.from(savedExpressions)}
                />
              </div>
            )}
          </div>

          {/* Factor Comparison */}
          <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
            <button
              type="button"
              onClick={() => setShowComparison(!showComparison)}
              className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <span className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-emerald-500" />
                因子对比
                <span className="text-xs text-gray-400 font-normal">并排比较多个因子表现</span>
              </span>
              {showComparison ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            {showComparison && (
              <div className="px-4 pb-4">
                <FactorComparison savedExpressions={Array.from(savedExpressions)} />
              </div>
            )}
          </div>

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
              <p className="mt-3 text-xs text-red-400">如果问题持续出现，欢迎点击右下角「反馈」按钮告诉我们，我们会尽快修复。</p>
            </div>
          )}

          {showResults && activeTask.result && (
            <ResultsDashboard
              result={activeTask.result}
              onSaveFactor={handleSaveFactor}
              isSaving={saving}
              isSaved={savedExpressions.has(activeTask.result.params.expression)}
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
      </div>
      <FeedbackButton />
    </div>
  );
}
