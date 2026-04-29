import { useState, useEffect, useCallback } from "react";
import { Loader2, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { useColorMode } from "../contexts/ColorModeContext";
import { authFetch } from "../api/client";
import { getReportUrl } from "../api/client";
import type { Task } from "../types/backtest";

interface Stats {
  total: number;
  completed: number;
  failed: number;
  running: number;
  success_rate: number;
  rating_distribution: Record<string, number>;
}

type StatusFilter = "all" | "completed" | "failed" | "running";
type RatingFilter = "all" | "A" | "B" | "C" | "D";

export default function ResearchDashboard() {
  const { isDark } = useColorMode();
  const [stats, setStats] = useState<Stats | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [ratingFilter, setRatingFilter] = useState<RatingFilter>("all");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const pageSize = 20;

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
      if (ratingFilter !== "all") url += `&rating=${ratingFilter}`;
      const res = await authFetch(url);
      if (res.ok) {
        const data = await res.json();
        setTasks(data.tasks || []);
      }
    } catch { /* ignore */ }
  }, [page, statusFilter, ratingFilter]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadTasks(); }, [loadTasks]);

  const hasActiveTasks = tasks.some((t) => t.status !== "completed" && t.status !== "failed");
  useEffect(() => {
    const interval = hasActiveTasks ? 5000 : 15000;
    const id = setInterval(() => { loadStats(); loadTasks(); }, interval);
    return () => clearInterval(id);
  }, [hasActiveTasks, loadStats, loadTasks]);

  const handleFilterChange = (f: StatusFilter) => {
    setStatusFilter(f);
    setPage(1);
  };

  const handleRatingFilter = (r: RatingFilter) => {
    setRatingFilter(r);
    setPage(1);
  };

  const cardClass = `rounded-xl border p-4 ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"}`;
  const textPrimary = isDark ? "text-gray-100" : "text-gray-900";
  const textSecondary = isDark ? "text-gray-400" : "text-gray-500";
  const textMuted = isDark ? "text-gray-500" : "text-gray-400";

  const ratingColor = (rating: string) => {
    if (rating === "A") return "bg-emerald-50 text-emerald-600 border-emerald-200";
    if (rating === "B") return "bg-blue-50 text-blue-600 border-blue-200";
    if (rating === "C") return "bg-yellow-50 text-yellow-600 border-yellow-200";
    if (rating === "D") return "bg-orange-50 text-orange-600 border-orange-200";
    return "bg-gray-50 text-gray-500 border-gray-200";
  };

  const ratingColorDark = (rating: string) => {
    if (rating === "A") return "bg-emerald-900/30 text-emerald-400 border-emerald-800";
    if (rating === "B") return "bg-blue-900/30 text-blue-400 border-blue-800";
    if (rating === "C") return "bg-yellow-900/30 text-yellow-400 border-yellow-800";
    if (rating === "D") return "bg-orange-900/30 text-orange-400 border-orange-800";
    return "bg-gray-800 text-gray-500 border-gray-700";
  };

  const statusText = (status: string) => {
    if (status === "completed") return <span className={`text-sm font-medium ${isDark ? "text-emerald-400" : "text-emerald-600"}`}>成功</span>;
    if (status === "failed") return <span className={`text-sm font-medium ${isDark ? "text-red-400" : "text-red-500"}`}>失败</span>;
    return <span className={`inline-flex items-center gap-1 text-sm font-medium ${isDark ? "text-blue-400" : "text-blue-500"}`}><Loader2 className="h-3.5 w-3.5 animate-spin" />运行中</span>;
  };

  const formatTime = (task: Task) => {
    const ca = (task as unknown as Record<string, unknown>).created_at as string | undefined;
    if (!ca) return "—";
    try {
      const d = new Date(ca);
      const Y = d.getFullYear();
      const M = String(d.getMonth() + 1).padStart(2, "0");
      const D = String(d.getDate()).padStart(2, "0");
      const h = String(d.getHours()).padStart(2, "0");
      const m = String(d.getMinutes()).padStart(2, "0");
      const s = String(d.getSeconds()).padStart(2, "0");
      return `${Y}/${M}/${D} ${h}:${m}:${s}`;
    } catch { return "—"; }
  };
  const formatDuration = (task: Task) => {
    const r = task as unknown as Record<string, unknown>;
    const dur = r.duration_seconds as number | undefined;
    if (dur != null && dur >= 0) {
      if (dur < 60) return `${dur.toFixed(1)}s`;
      return `${Math.floor(dur / 60)}m${Math.round(dur % 60)}s`;
    }
    if (task.status !== "completed" && task.status !== "failed") {
      const ca = r.created_at as string | undefined;
      if (ca) {
        const elapsed = (Date.now() - new Date(ca).getTime()) / 1000;
        if (elapsed > 0 && elapsed < 3600) return `${elapsed.toFixed(0)}s…`;
      }
    }
    return "—";
  };
  const getExpression = (task: Task) => task.expression || task.result?.params?.expression || (task.params as unknown as Record<string, unknown>)?.expression as string || "—";
  const getPrompt = (task: Task) => (task.params as unknown as Record<string, unknown>)?.prompt as string || task.result?.llm?.prompt || "—";
  const getRating = (task: Task) => task.result?.interpretation?.rating || (task.result?.backtest_summary as unknown as Record<string, unknown>)?.wq_rating as string || "";

  const thClass = `text-left px-6 py-4 text-sm font-semibold ${isDark ? "text-gray-400" : "text-gray-500"}`;
  const thCenter = `text-center px-5 py-4 text-sm font-semibold ${isDark ? "text-gray-400" : "text-gray-500"}`;

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className={cardClass}>
            <p className={`text-xs font-medium ${textSecondary}`}>总任务</p>
            <p className={`text-2xl font-bold mt-1 ${textPrimary}`}>{stats.total}</p>
          </div>
          <div className={cardClass}>
            <p className={`text-xs font-medium ${textSecondary}`}>已完成</p>
            <p className="text-2xl font-bold mt-1 text-emerald-500">{stats.completed}</p>
          </div>
          <div className={cardClass}>
            <p className={`text-xs font-medium ${textSecondary}`}>进行中</p>
            <p className="text-2xl font-bold mt-1 text-blue-500">{stats.running}</p>
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
            <div className={`${cardClass} col-span-2 md:col-span-5`}>
              <p className={`text-xs font-medium mb-2 ${textSecondary}`}>评分分布（点击筛选）</p>
              <div className="flex gap-3 flex-wrap">
                {["A", "B", "C", "D"].map((r) => {
                  const count = stats.rating_distribution[r] || 0;
                  if (!count) return null;
                  const isActive = ratingFilter === r;
                  return (
                    <button
                      key={r}
                      onClick={() => handleRatingFilter(isActive ? "all" : r as RatingFilter)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium border transition-all cursor-pointer ${isDark ? ratingColorDark(r) : ratingColor(r)} ${isActive ? "ring-2 ring-offset-1 ring-blue-500 scale-105" : "hover:scale-105"}`}
                    >
                      {r} <span className="font-bold">{count}</span>
                    </button>
                  );
                })}
                {ratingFilter !== "all" && (
                  <button
                    onClick={() => handleRatingFilter("all")}
                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium transition-colors ${isDark ? "text-gray-400 hover:bg-gray-800" : "text-gray-500 hover:bg-gray-100"}`}
                  >
                    清除筛选
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        {(["all", "completed", "running", "failed"] as StatusFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => handleFilterChange(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              statusFilter === f
                ? isDark ? "bg-blue-500/20 text-blue-400 border border-blue-500/30" : "bg-blue-50 text-blue-700 border border-blue-200"
                : isDark ? "text-gray-400 hover:bg-gray-800" : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            {f === "all" ? "全部" : f === "completed" ? "已完成" : f === "running" ? "进行中" : "失败"}
          </button>
        ))}

        <span className={`mx-1 ${textSecondary}`}>|</span>

        {(["all", "A", "B", "C", "D"] as RatingFilter[]).map((r) => (
          <button
            key={`r-${r}`}
            onClick={() => handleRatingFilter(r)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              ratingFilter === r
                ? r === "all"
                  ? isDark ? "bg-blue-500/20 text-blue-400 border border-blue-500/30" : "bg-blue-50 text-blue-700 border border-blue-200"
                  : `border ${isDark ? ratingColorDark(r) : ratingColor(r)} ring-1 ring-blue-500`
                : r === "all"
                  ? isDark ? "text-gray-400 hover:bg-gray-800" : "text-gray-500 hover:bg-gray-100"
                  : isDark ? "text-gray-400 hover:bg-gray-800" : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            {r === "all" ? "全部评级" : `${r} 级`}
          </button>
        ))}
      </div>

      {/* Task table */}
      <div className={`rounded-xl border overflow-hidden ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"}`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className={isDark ? "bg-gray-800/60 border-b border-gray-700" : "bg-gray-50/80 border-b border-gray-200"}>
              <tr>
                <th className={thClass}>任务ID</th>
                <th className={thClass}>Prompt</th>
                <th className={thClass}>表达式</th>
                <th className={thCenter}>评级</th>
                <th className={thCenter}>状态</th>
                <th className={thCenter}>耗时</th>
                <th className={thCenter}>时间</th>
              </tr>
            </thead>
            <tbody className={isDark ? "divide-y divide-gray-800" : "divide-y divide-gray-100"}>
              {tasks.length === 0 && (
                <tr><td colSpan={7} className={`text-center py-16 ${textSecondary}`}>暂无任务</td></tr>
              )}
              {tasks.map((task) => {
                const rating = getRating(task);
                const expression = getExpression(task);
                return (
                  <tr
                    key={task.task_id}
                    onClick={() => setSelectedTask(task)}
                    className={`cursor-pointer transition-colors ${isDark ? "hover:bg-gray-800/40" : "hover:bg-gray-50/70"}`}
                  >
                    <td className={`px-6 py-5 font-mono text-sm ${textMuted} whitespace-nowrap`}>{task.task_id}</td>
                    <td className={`px-6 py-5 max-w-[360px] truncate text-sm ${textPrimary}`}>{getPrompt(task)}</td>
                    <td className={`px-6 py-5 max-w-[380px] truncate font-mono text-sm ${textSecondary}`}>{expression}</td>
                    <td className="px-5 py-5 text-center">
                      {rating ? (
                        <span className={`inline-block px-2.5 py-0.5 rounded-md text-sm font-bold border ${isDark ? ratingColorDark(rating) : ratingColor(rating)}`}>{rating}</span>
                      ) : (
                        <span className={textMuted}>-</span>
                      )}
                    </td>
                    <td className="px-5 py-5 text-center whitespace-nowrap">{statusText(task.status)}</td>
                    <td className={`px-5 py-5 text-center font-mono text-sm ${textMuted} whitespace-nowrap`}>{formatDuration(task)}</td>
                    <td className={`px-5 py-5 text-center text-sm ${textMuted} whitespace-nowrap`}>{formatTime(task)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-center gap-3">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className={`p-1.5 rounded-lg transition-colors ${page === 1 ? "opacity-30 cursor-not-allowed" : isDark ? "hover:bg-gray-800 text-gray-400" : "hover:bg-gray-100 text-gray-600"}`}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className={`text-sm ${textSecondary}`}>第 {page} 页</span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={tasks.length < pageSize}
          className={`p-1.5 rounded-lg transition-colors ${tasks.length < pageSize ? "opacity-30 cursor-not-allowed" : isDark ? "hover:bg-gray-800 text-gray-400" : "hover:bg-gray-100 text-gray-600"}`}
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
                {statusText(selectedTask.status)}
                {getRating(selectedTask) && (
                  <span className={`px-2 py-0.5 rounded text-sm font-bold border ${isDark ? ratingColorDark(getRating(selectedTask)) : ratingColor(getRating(selectedTask))}`}>{getRating(selectedTask)}</span>
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
