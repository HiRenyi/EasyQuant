import { useState, useEffect, useCallback } from "react";
import { CheckCircle2, XCircle, Loader2, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { useColorMode } from "../contexts/ColorModeContext";
import { authFetch } from "../api/client";
import { getReportUrl } from "../api/client";
import type { Task } from "../types/backtest";

interface Stats {
  total: number;
  completed: number;
  failed: number;
  success_rate: number;
  rating_distribution: Record<string, number>;
}

type StatusFilter = "all" | "completed" | "failed";

export default function ResearchDashboard() {
  const { isDark } = useColorMode();
  const [stats, setStats] = useState<Stats | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const pageSize = 15;

  const loadStats = useCallback(async () => {
    try {
      const res = await authFetch("/api/v1/tasks/stats");
      if (res.ok) setStats(await res.json());
    } catch { /* ignore */ }
  }, []);

  const loadTasks = useCallback(async () => {
    try {
      let url = `/api/v1/tasks?page=${page}&page_size=${pageSize}`;
      if (statusFilter !== "all") url += `&status=${statusFilter}`;
      const res = await authFetch(url);
      if (res.ok) {
        const data = await res.json();
        setTasks(data.tasks || []);
      }
    } catch { /* ignore */ }
  }, [page, statusFilter]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadTasks(); }, [loadTasks]);

  const hasActiveTasks = tasks.some((t) => t.status !== "completed" && t.status !== "failed");
  useEffect(() => {
    if (!hasActiveTasks) return;
    const id = setInterval(() => { loadStats(); loadTasks(); }, 5000);
    return () => clearInterval(id);
  }, [hasActiveTasks, loadStats, loadTasks]);

  const handleFilterChange = (f: StatusFilter) => {
    setStatusFilter(f);
    setPage(1);
  };

  const cardClass = `rounded-xl border p-4 ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"}`;
  const textPrimary = isDark ? "text-gray-100" : "text-gray-900";
  const textSecondary = isDark ? "text-gray-400" : "text-gray-500";

  const ratingColor = (rating: string) => {
    if (rating === "A") return "bg-emerald-100 text-emerald-700 border-emerald-200";
    if (rating === "B") return "bg-blue-100 text-blue-700 border-blue-200";
    if (rating === "C") return "bg-yellow-100 text-yellow-700 border-yellow-200";
    if (rating === "D") return "bg-orange-100 text-orange-700 border-orange-200";
    return "bg-gray-100 text-gray-600 border-gray-200";
  };

  const statusBadge = (status: string) => {
    if (status === "completed") return <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600"><CheckCircle2 className="h-3 w-3" />完成</span>;
    if (status === "failed") return <span className="inline-flex items-center gap-1 text-xs font-medium text-red-500"><XCircle className="h-3 w-3" />失败</span>;
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-500"><Loader2 className="h-3 w-3 animate-spin" />进行中</span>;
  };

  const getExpression = (task: Task) => task.expression || task.result?.params?.expression || (task.params as unknown as Record<string, unknown>)?.expression as string || "—";
  const getPrompt = (task: Task) => (task.params as unknown as Record<string, unknown>)?.prompt as string || task.result?.llm?.prompt || "—";
  const getRating = (task: Task) => task.result?.interpretation?.rating || (task.result?.backtest_summary as unknown as Record<string, unknown>)?.wq_rating as string || "";
  const getSharpe = (task: Task) => task.result?.backtest_summary?.long_short_sharpe;
  const getFitness = (task: Task) => task.result?.wq_brain?.wq_fitness ?? task.result?.backtest_summary?.wq_fitness;
  const getIC = (task: Task) => task.result?.backtest_summary?.rank_ic_mean;
  const getTurnover = (task: Task) => task.result?.backtest_summary?.turnover;

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className={cardClass}>
            <p className={`text-xs font-medium ${textSecondary}`}>总任务</p>
            <p className={`text-2xl font-bold mt-1 ${textPrimary}`}>{stats.total}</p>
          </div>
          <div className={cardClass}>
            <p className={`text-xs font-medium ${textSecondary}`}>已完成</p>
            <p className="text-2xl font-bold mt-1 text-emerald-500">{stats.completed}</p>
          </div>
          <div className={cardClass}>
            <p className={`text-xs font-medium ${textSecondary}`}>失败</p>
            <p className="text-2xl font-bold mt-1 text-red-500">{stats.failed}</p>
          </div>
          <div className={cardClass}>
            <p className={`text-xs font-medium ${textSecondary}`}>成功率</p>
            <p className={`text-2xl font-bold mt-1 ${textPrimary}`}>{stats.success_rate}%</p>
          </div>
          {Object.keys(stats.rating_distribution).length > 0 && (
            <div className={`${cardClass} col-span-2 md:col-span-4`}>
              <p className={`text-xs font-medium mb-2 ${textSecondary}`}>评分分布</p>
              <div className="flex gap-3 flex-wrap">
                {["A", "B", "C", "D"].map((r) => {
                  const count = stats.rating_distribution[r] || 0;
                  if (!count) return null;
                  return (
                    <span key={r} className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium border ${ratingColor(r)}`}>
                      {r} <span className="font-bold">{count}</span>
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2">
        {(["all", "completed", "failed"] as StatusFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => handleFilterChange(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              statusFilter === f
                ? isDark ? "bg-blue-500/20 text-blue-400 border border-blue-500/30" : "bg-blue-50 text-blue-700 border border-blue-200"
                : isDark ? "text-gray-400 hover:bg-gray-800" : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            {f === "all" ? "全部" : f === "completed" ? "已完成" : "失败"}
          </button>
        ))}
      </div>

      {/* Task table */}
      <div className={`rounded-xl border overflow-hidden ${isDark ? "border-gray-700" : "border-gray-200"}`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className={isDark ? "bg-gray-800/50" : "bg-gray-50"}>
              <tr>
                <th className={`text-left px-4 py-3 font-medium ${textSecondary}`}>描述</th>
                <th className={`text-left px-4 py-3 font-medium ${textSecondary}`}>表达式</th>
                <th className={`text-center px-4 py-3 font-medium ${textSecondary}`}>评分</th>
                <th className={`text-center px-4 py-3 font-medium ${textSecondary}`}>Sharpe</th>
                <th className={`text-center px-4 py-3 font-medium ${textSecondary}`}>Fitness</th>
                <th className={`text-center px-4 py-3 font-medium ${textSecondary}`}>IC</th>
                <th className={`text-center px-4 py-3 font-medium ${textSecondary}`}>Turnover</th>
                <th className={`text-center px-4 py-3 font-medium ${textSecondary}`}>状态</th>
                <th className={`text-center px-4 py-3 font-medium ${textSecondary}`}>报告</th>
              </tr>
            </thead>
            <tbody>
              {tasks.length === 0 && (
                <tr><td colSpan={9} className={`text-center py-12 ${textSecondary}`}>暂无任务</td></tr>
              )}
              {tasks.map((task) => {
                const rating = getRating(task);
                const sharpe = getSharpe(task);
                const fitness = getFitness(task);
                const ic = getIC(task);
                const turnover = getTurnover(task);
                return (
                  <tr
                    key={task.task_id}
                    onClick={() => setSelectedTask(task)}
                    className={`border-t cursor-pointer transition-colors ${
                      isDark ? "border-gray-800 hover:bg-gray-800/50" : "border-gray-100 hover:bg-gray-50"
                    }`}
                  >
                    <td className={`px-4 py-3 max-w-[180px] truncate ${textPrimary}`}>{getPrompt(task)}</td>
                    <td className={`px-4 py-3 max-w-[220px] truncate font-mono text-xs ${textSecondary}`}>{getExpression(task)}</td>
                    <td className="px-4 py-3 text-center">
                      {rating && <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold border ${ratingColor(rating)}`}>{rating}</span>}
                    </td>
                    <td className={`px-4 py-3 text-center font-mono text-xs ${textPrimary}`}>{sharpe != null ? sharpe.toFixed(2) : "—"}</td>
                    <td className={`px-4 py-3 text-center font-mono text-xs ${textPrimary}`}>{fitness != null ? (fitness as number).toFixed(3) : "—"}</td>
                    <td className={`px-4 py-3 text-center font-mono text-xs ${textPrimary}`}>{ic != null ? (ic as number).toFixed(4) : "—"}</td>
                    <td className={`px-4 py-3 text-center font-mono text-xs ${textPrimary}`}>{turnover != null ? (turnover as number).toFixed(3) : "—"}</td>
                    <td className="px-4 py-3 text-center">{statusBadge(task.status)}</td>
                    <td className="px-4 py-3 text-center">
                      {task.result?.report_url && (
                        <a
                          href={getReportUrl(task.result.report_url)}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-blue-500 hover:text-blue-400"
                        >
                          <ExternalLink className="h-4 w-4 inline" />
                        </a>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-center gap-2">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className={`p-1.5 rounded-lg ${page === 1 ? "opacity-30 cursor-not-allowed" : isDark ? "hover:bg-gray-800 text-gray-400" : "hover:bg-gray-100 text-gray-600"}`}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className={`text-sm ${textSecondary}`}>第 {page} 页</span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={tasks.length < pageSize}
          className={`p-1.5 rounded-lg ${tasks.length < pageSize ? "opacity-30 cursor-not-allowed" : isDark ? "hover:bg-gray-800 text-gray-400" : "hover:bg-gray-100 text-gray-600"}`}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* Detail modal */}
      {selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setSelectedTask(null)}>
          <div
            className={`w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-2xl border p-6 shadow-xl ${isDark ? "bg-gray-900 border-gray-700" : "bg-white border-gray-200"}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className={`text-lg font-semibold ${textPrimary}`}>任务详情</h3>
              <button onClick={() => setSelectedTask(null)} className={`text-sm ${textSecondary} hover:${textPrimary}`}>关闭</button>
            </div>

            <div className="space-y-4">
              {/* Prompt */}
              <div>
                <p className={`text-xs font-medium mb-1 ${textSecondary}`}>描述</p>
                <p className={`text-sm ${textPrimary}`}>{getPrompt(selectedTask)}</p>
              </div>

              {/* Expression */}
              <div>
                <p className={`text-xs font-medium mb-1 ${textSecondary}`}>表达式</p>
                <p className={`text-sm font-mono p-2 rounded-lg ${isDark ? "bg-gray-800" : "bg-gray-50"} ${textPrimary}`}>{getExpression(selectedTask)}</p>
              </div>

              {/* Status + Error */}
              <div className="flex items-center gap-3">
                {statusBadge(selectedTask.status)}
                {getRating(selectedTask) && (
                  <span className={`px-2 py-0.5 rounded text-xs font-bold border ${ratingColor(getRating(selectedTask))}`}>{getRating(selectedTask)}</span>
                )}
              </div>
              {selectedTask.error && (
                <div className={`text-sm p-3 rounded-lg ${isDark ? "bg-red-900/30 text-red-400" : "bg-red-50 text-red-600"}`}>
                  {typeof selectedTask.error === "string" ? selectedTask.error : JSON.stringify(selectedTask.error)}
                </div>
              )}

              {/* Metrics */}
              {selectedTask.result?.backtest_summary && (
                <div>
                  <p className={`text-xs font-medium mb-2 ${textSecondary}`}>核心指标</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { label: "L/S Sharpe", value: selectedTask.result.backtest_summary.long_short_sharpe?.toFixed(2) },
                      { label: "L/S Annual", value: selectedTask.result.backtest_summary.long_short_annual != null ? `${(selectedTask.result.backtest_summary.long_short_annual * 100).toFixed(1)}%` : undefined },
                      { label: "Rank IC", value: (selectedTask.result.backtest_summary.rank_ic_mean as number | undefined)?.toFixed(4) },
                      { label: "IC IR", value: (selectedTask.result.backtest_summary.ic_ir as number | undefined)?.toFixed(2) },
                      { label: "Turnover", value: (selectedTask.result.backtest_summary.turnover as number | undefined)?.toFixed(3) },
                      { label: "Fitness", value: (selectedTask.result.backtest_summary.wq_fitness as number | undefined)?.toFixed(3) },
                      { label: "Monotonicity", value: selectedTask.result.backtest_summary.monotonicity_score?.toFixed(2) },
                      { label: "Spread", value: selectedTask.result.backtest_summary.spread?.toFixed(2) },
                    ].map(({ label, value }) => value != null ? (
                      <div key={label} className={`p-2 rounded-lg ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
                        <p className={`text-xs ${textSecondary}`}>{label}</p>
                        <p className={`text-sm font-mono font-semibold ${textPrimary}`}>{value}</p>
                      </div>
                    ) : null)}
                  </div>
                </div>
              )}

              {/* WQ Brain */}
              {selectedTask.result?.wq_brain && (
                <div>
                  <p className={`text-xs font-medium mb-2 ${textSecondary}`}>WQ BRAIN 模拟</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { label: "WQ Sharpe", value: selectedTask.result.wq_brain.wq_sharpe.toFixed(2) },
                      { label: "WQ Fitness", value: selectedTask.result.wq_brain.wq_fitness.toFixed(3) },
                      { label: "WQ Returns", value: `${(selectedTask.result.wq_brain.wq_returns * 100).toFixed(1)}%` },
                      { label: "WQ Rating", value: selectedTask.result.wq_brain.wq_rating },
                    ].map(({ label, value }) => (
                      <div key={label} className={`p-2 rounded-lg ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
                        <p className={`text-xs ${textSecondary}`}>{label}</p>
                        <p className={`text-sm font-mono font-semibold ${textPrimary}`}>{value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Interpretation */}
              {selectedTask.result?.interpretation && (
                <div>
                  <p className={`text-xs font-medium mb-2 ${textSecondary}`}>AI 分析</p>
                  <div className={`p-3 rounded-lg space-y-2 text-sm ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
                    {selectedTask.result.interpretation.conclusion && (
                      <p className={textPrimary}><span className={`font-medium ${textSecondary}`}>结论：</span>{selectedTask.result.interpretation.conclusion}</p>
                    )}
                    {selectedTask.result.interpretation.logic && (
                      <p className={textPrimary}><span className={`font-medium ${textSecondary}`}>逻辑：</span>{selectedTask.result.interpretation.logic}</p>
                    )}
                    {selectedTask.result.interpretation.guidance && (
                      <p className={textPrimary}><span className={`font-medium ${textSecondary}`}>建议：</span>{selectedTask.result.interpretation.guidance}</p>
                    )}
                  </div>
                </div>
              )}

              {/* Report link */}
              {selectedTask.result?.report_url && (
                <a
                  href={getReportUrl(selectedTask.result.report_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
                >
                  <ExternalLink className="h-4 w-4" />
                  查看完整报告
                </a>
              )}

              {/* Params */}
              {selectedTask.result?.params && (
                <div>
                  <p className={`text-xs font-medium mb-1 ${textSecondary}`}>回测参数</p>
                  <p className={`text-xs font-mono ${textSecondary}`}>
                    {selectedTask.result.params.universe} · {selectedTask.result.params.start_date} ~ {selectedTask.result.params.end_date} · {selectedTask.result.params.n_groups}组 · 持仓{selectedTask.result.params.holding_period}天 · {selectedTask.result.params.stock_count}只
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
