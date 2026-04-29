import { useState, useEffect, useCallback } from "react";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
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

const IconTasks = () => (
  <svg className="w-5 h-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="14" height="14" rx="2" /><path d="M7 7h6M7 10h6M7 13h4" />
  </svg>
);
const IconCheck = () => (
  <svg className="w-5 h-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="10" cy="10" r="7" /><path d="M7 10l2 2 4-4" />
  </svg>
);
const IconPulse = () => (
  <svg className="w-5 h-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 10h4l2-5 3 10 2-5h5" />
  </svg>
);
const IconAlert = () => (
  <svg className="w-5 h-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 3l7 12H3L10 3z" /><path d="M10 9v2M10 13v.5" />
  </svg>
);
const IconPercent = () => (
  <svg className="w-5 h-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="7" cy="7" r="2" /><circle cx="13" cy="13" r="2" /><path d="M15 5L5 15" />
  </svg>
);
const IconBrain = () => (
  <svg className="w-4 h-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 2C7.5 2 5 4 5 7c0 1.5.5 2.5 1 3.5S5 13 5 14c0 2 2 4 5 4s5-2 5-4c0-1-.5-2.5 0-3.5S15 8.5 15 7c0-3-2.5-5-5-5z" />
    <path d="M10 2v16M7 5c1 1 2 1 3 0M7 9c1 1 2 1 3 0M7 13c1 1 2 1 3 0M13 5c-1 1-2 1-3 0M13 9c-1 1-2 1-3 0M13 13c-1 1-2 1-3 0" />
  </svg>
);
const IconSpinner = () => (
  <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="8" cy="8" r="6" strokeOpacity="0.25" /><path d="M14 8a6 6 0 00-6-6" />
  </svg>
);
const IconSuccessDot = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.5" /><path d="M4.5 7l2 2 3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
);
const IconFailDot = () => (
  <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.5" /><path d="M5 5l4 4M9 5l-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
);

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

  const handleFilterChange = (f: StatusFilter) => { setStatusFilter(f); setPage(1); };
  const handleRatingFilter = (r: RatingFilter) => { setRatingFilter(r); setPage(1); };

  const surface = isDark ? "bg-[#0d1117]" : "bg-white";
  const surfaceAlt = isDark ? "bg-[#161b22]" : "bg-gray-50/80";
  const border = isDark ? "border-[#21262d]" : "border-gray-200";
  const textPrimary = isDark ? "text-gray-100" : "text-gray-900";
  const textSecondary = isDark ? "text-gray-400" : "text-gray-500";
  const textMuted = isDark ? "text-gray-500" : "text-gray-400";
  const hoverRow = isDark ? "hover:bg-[#1c2128]" : "hover:bg-slate-50";

  const ratingColor = (rating: string) => {
    if (rating === "A") return "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (rating === "B") return "bg-sky-50 text-sky-700 border-sky-200";
    if (rating === "C") return "bg-amber-50 text-amber-700 border-amber-200";
    if (rating === "D") return "bg-orange-50 text-orange-600 border-orange-200";
    return "bg-gray-50 text-gray-500 border-gray-200";
  };
  const ratingColorDark = (rating: string) => {
    if (rating === "A") return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
    if (rating === "B") return "bg-sky-500/10 text-sky-400 border-sky-500/30";
    if (rating === "C") return "bg-amber-500/10 text-amber-400 border-amber-500/30";
    if (rating === "D") return "bg-orange-500/10 text-orange-400 border-orange-500/30";
    return "bg-gray-800 text-gray-500 border-gray-700";
  };

  const statusBadge = (status: string) => {
    if (status === "completed") return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-sm font-medium border ${isDark ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" : "bg-emerald-50 text-emerald-700 border-emerald-200"}`}>
        <IconSuccessDot />成功
      </span>
    );
    if (status === "failed") return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-sm font-medium border ${isDark ? "bg-red-500/10 text-red-400 border-red-500/30" : "bg-red-50 text-red-600 border-red-200"}`}>
        <IconFailDot />失败
      </span>
    );
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-sm font-medium border ${isDark ? "bg-blue-500/10 text-blue-400 border-blue-500/30" : "bg-blue-50 text-blue-600 border-blue-200"}`}>
        <IconSpinner />运行中
      </span>
    );
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
        if (elapsed > 0 && elapsed < 3600) return `${elapsed.toFixed(0)}s...`;
      }
    }
    return "—";
  };
  const getExpression = (task: Task) => task.expression || task.result?.params?.expression || (task.params as unknown as Record<string, unknown>)?.expression as string || "—";
  const getPrompt = (task: Task) => (task.params as unknown as Record<string, unknown>)?.prompt as string || task.result?.llm?.prompt || "—";
  const getRating = (task: Task) => task.result?.interpretation?.rating || (task.result?.backtest_summary as unknown as Record<string, unknown>)?.wq_rating as string || "";

  const thClass = `text-left px-6 py-3.5 text-xs font-semibold uppercase tracking-wider ${isDark ? "text-gray-500" : "text-gray-400"}`;
  const thCenter = `text-center px-5 py-3.5 text-xs font-semibold uppercase tracking-wider ${isDark ? "text-gray-500" : "text-gray-400"}`;

  const statCards = stats ? [
    { label: "Total Tasks", value: stats.total, icon: <IconTasks />, accent: isDark ? "text-gray-100" : "text-gray-900" },
    { label: "Completed", value: stats.completed, icon: <IconCheck />, accent: "text-emerald-500" },
    { label: "Running", value: stats.running, icon: <IconPulse />, accent: "text-blue-500" },
    { label: "Failed", value: stats.failed, icon: <IconAlert />, accent: "text-red-500" },
    { label: "Success Rate", value: `${stats.success_rate}%`, icon: <IconPercent />, accent: isDark ? "text-gray-100" : "text-gray-900" },
  ] : [];

  return (
    <div className="space-y-5">
      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {statCards.map(({ label, value, icon, accent }) => (
            <div key={label} className={`rounded-lg border ${border} ${surface} p-4 flex items-start gap-3`}>
              <div className={`mt-0.5 ${textMuted}`}>{icon}</div>
              <div>
                <p className={`text-xs font-medium uppercase tracking-wider ${textMuted}`}>{label}</p>
                <p className={`text-2xl font-bold tabular-nums mt-0.5 ${accent}`}>{value}</p>
              </div>
            </div>
          ))}
          {Object.keys(stats.rating_distribution).length > 0 && (
            <div className={`col-span-2 md:col-span-5 rounded-lg border ${border} ${surface} p-4`}>
              <p className={`text-xs font-medium uppercase tracking-wider mb-3 ${textMuted}`}>Rating Distribution</p>
              <div className="flex gap-2.5 flex-wrap">
                {["A", "B", "C", "D"].map((r) => {
                  const count = stats.rating_distribution[r] || 0;
                  if (!count) return null;
                  const isActive = ratingFilter === r;
                  return (
                    <button
                      key={r}
                      onClick={() => handleRatingFilter(isActive ? "all" : r as RatingFilter)}
                      className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-semibold border transition-all cursor-pointer ${isDark ? ratingColorDark(r) : ratingColor(r)} ${isActive ? "ring-2 ring-offset-1 ring-blue-500 shadow-sm" : "hover:shadow-sm"}`}
                    >
                      {r} <span className="font-mono">{count}</span>
                    </button>
                  );
                })}
                {ratingFilter !== "all" && (
                  <button
                    onClick={() => handleRatingFilter("all")}
                    className={`inline-flex items-center px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${isDark ? "text-gray-400 hover:bg-gray-800" : "text-gray-500 hover:bg-gray-100"}`}
                  >
                    Reset
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className={`flex items-center gap-1.5 flex-wrap rounded-lg border ${border} ${surface} px-3 py-2`}>
        {(["all", "completed", "running", "failed"] as StatusFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => handleFilterChange(f)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              statusFilter === f
                ? isDark ? "bg-blue-500/15 text-blue-400" : "bg-blue-50 text-blue-700"
                : isDark ? "text-gray-400 hover:text-gray-200 hover:bg-[#1c2128]" : "text-gray-500 hover:text-gray-900 hover:bg-gray-100"
            }`}
          >
            {f === "all" ? "ALL" : f === "completed" ? "COMPLETED" : f === "running" ? "RUNNING" : "FAILED"}
          </button>
        ))}

        <div className={`w-px h-5 mx-1.5 ${isDark ? "bg-[#21262d]" : "bg-gray-200"}`} />

        {(["all", "A", "B", "C", "D"] as RatingFilter[]).map((r) => (
          <button
            key={`r-${r}`}
            onClick={() => handleRatingFilter(r)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              ratingFilter === r
                ? r === "all"
                  ? isDark ? "bg-blue-500/15 text-blue-400" : "bg-blue-50 text-blue-700"
                  : `border ${isDark ? ratingColorDark(r) : ratingColor(r)} ring-1 ring-blue-500`
                : isDark ? "text-gray-400 hover:text-gray-200 hover:bg-[#1c2128]" : "text-gray-500 hover:text-gray-900 hover:bg-gray-100"
            }`}
          >
            {r === "all" ? "ALL RATINGS" : `GRADE ${r}`}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className={`rounded-lg border overflow-hidden ${border} ${surface}`}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className={`${surfaceAlt} border-b ${border}`}>
                <th className={thClass}>Task ID</th>
                <th className={thClass}>Prompt</th>
                <th className={thClass}>Expression</th>
                <th className={thCenter}>Grade</th>
                <th className={thCenter}>Status</th>
                <th className={thCenter}>Duration</th>
                <th className={thCenter}>Timestamp</th>
              </tr>
            </thead>
            <tbody className={isDark ? "divide-y divide-[#21262d]" : "divide-y divide-gray-100"}>
              {tasks.length === 0 && (
                <tr><td colSpan={7} className={`text-center py-20 ${textMuted}`}>
                  <div className="flex flex-col items-center gap-2">
                    <IconBrain />
                    <span className="text-sm">No research tasks yet</span>
                  </div>
                </td></tr>
              )}
              {tasks.map((task) => {
                const rating = getRating(task);
                const expression = getExpression(task);
                return (
                  <tr
                    key={task.task_id}
                    onClick={() => setSelectedTask(task)}
                    className={`cursor-pointer transition-colors ${hoverRow}`}
                  >
                    <td className={`px-6 py-4 font-mono text-sm ${textMuted} whitespace-nowrap`}>{task.task_id}</td>
                    <td className={`px-6 py-4 max-w-[360px] truncate text-sm ${textPrimary}`}>{getPrompt(task)}</td>
                    <td className={`px-6 py-4 max-w-[380px] truncate font-mono text-sm ${textSecondary}`}>{expression}</td>
                    <td className="px-5 py-4 text-center">
                      {rating ? (
                        <span className={`inline-block px-2.5 py-0.5 rounded-md text-xs font-bold border ${isDark ? ratingColorDark(rating) : ratingColor(rating)}`}>{rating}</span>
                      ) : (
                        <span className={textMuted}>-</span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-center whitespace-nowrap">{statusBadge(task.status)}</td>
                    <td className={`px-5 py-4 text-center font-mono text-sm tabular-nums ${textMuted} whitespace-nowrap`}>{formatDuration(task)}</td>
                    <td className={`px-5 py-4 text-center font-mono text-sm tabular-nums ${textMuted} whitespace-nowrap`}>{formatTime(task)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-center gap-4">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className={`p-1.5 rounded-md transition-colors ${page === 1 ? "opacity-30 cursor-not-allowed" : isDark ? "hover:bg-[#1c2128] text-gray-400" : "hover:bg-gray-100 text-gray-600"}`}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className={`text-xs font-mono uppercase tracking-wider ${textMuted}`}>Page {page}</span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={tasks.length < pageSize}
          className={`p-1.5 rounded-md transition-colors ${tasks.length < pageSize ? "opacity-30 cursor-not-allowed" : isDark ? "hover:bg-[#1c2128] text-gray-400" : "hover:bg-gray-100 text-gray-600"}`}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* Detail modal */}
      {selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setSelectedTask(null)}>
          <div
            className={`w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-xl border shadow-2xl ${border} ${surface} p-6`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2.5">
                <div className={`p-1.5 rounded-md ${isDark ? "bg-blue-500/10 text-blue-400" : "bg-blue-50 text-blue-600"}`}>
                  <IconBrain />
                </div>
                <h3 className={`text-lg font-semibold ${textPrimary}`}>Task Detail</h3>
                <span className={`font-mono text-xs ${textMuted}`}>{selectedTask.task_id}</span>
              </div>
              <button onClick={() => setSelectedTask(null)} className={`p-1.5 rounded-md transition-colors ${isDark ? "text-gray-400 hover:bg-[#1c2128]" : "text-gray-400 hover:bg-gray-100"}`}>
                <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 4l8 8M12 4l-8 8" /></svg>
              </button>
            </div>

            <div className="space-y-5">
              <div>
                <p className={`text-xs font-medium uppercase tracking-wider mb-1.5 ${textMuted}`}>Prompt</p>
                <p className={`text-sm leading-relaxed ${textPrimary}`}>{getPrompt(selectedTask)}</p>
              </div>

              <div>
                <p className={`text-xs font-medium uppercase tracking-wider mb-1.5 ${textMuted}`}>Expression</p>
                <div className={`font-mono text-sm p-3 rounded-lg border ${border} ${surfaceAlt} ${textPrimary}`}>{getExpression(selectedTask)}</div>
              </div>

              <div className="flex items-center gap-3">
                {statusBadge(selectedTask.status)}
                {getRating(selectedTask) && (
                  <span className={`px-2.5 py-0.5 rounded-md text-xs font-bold border ${isDark ? ratingColorDark(getRating(selectedTask)) : ratingColor(getRating(selectedTask))}`}>{getRating(selectedTask)}</span>
                )}
              </div>
              {selectedTask.error && (
                <div className={`text-sm p-3 rounded-lg border ${isDark ? "bg-red-500/10 text-red-400 border-red-500/20" : "bg-red-50 text-red-600 border-red-200"}`}>
                  {typeof selectedTask.error === "string" ? selectedTask.error : JSON.stringify(selectedTask.error)}
                </div>
              )}

              {selectedTask.result?.backtest_summary && (
                <div>
                  <p className={`text-xs font-medium uppercase tracking-wider mb-2.5 ${textMuted}`}>Key Metrics</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
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
                      <div key={label} className={`p-2.5 rounded-lg border ${border} ${surfaceAlt}`}>
                        <p className={`text-xs ${textMuted}`}>{label}</p>
                        <p className={`text-sm font-mono font-semibold tabular-nums mt-0.5 ${textPrimary}`}>{value}</p>
                      </div>
                    ) : null)}
                  </div>
                </div>
              )}

              {selectedTask.result?.wq_brain && (
                <div>
                  <p className={`text-xs font-medium uppercase tracking-wider mb-2.5 ${textMuted}`}>WQ BRAIN Simulation</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
                    {[
                      { label: "WQ Sharpe", value: selectedTask.result.wq_brain.wq_sharpe.toFixed(2) },
                      { label: "WQ Fitness", value: selectedTask.result.wq_brain.wq_fitness.toFixed(3) },
                      { label: "WQ Returns", value: `${(selectedTask.result.wq_brain.wq_returns * 100).toFixed(1)}%` },
                      { label: "WQ Rating", value: selectedTask.result.wq_brain.wq_rating },
                    ].map(({ label, value }) => (
                      <div key={label} className={`p-2.5 rounded-lg border ${border} ${surfaceAlt}`}>
                        <p className={`text-xs ${textMuted}`}>{label}</p>
                        <p className={`text-sm font-mono font-semibold tabular-nums mt-0.5 ${textPrimary}`}>{value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedTask.result?.interpretation && (
                <div>
                  <div className={`flex items-center gap-1.5 mb-2.5 ${textMuted}`}>
                    <IconBrain />
                    <p className="text-xs font-medium uppercase tracking-wider">AI Analysis</p>
                  </div>
                  <div className={`p-3.5 rounded-lg border space-y-2.5 text-sm ${border} ${surfaceAlt}`}>
                    {selectedTask.result.interpretation.conclusion && (
                      <p className={textPrimary}><span className={`font-semibold ${textSecondary}`}>Conclusion: </span>{selectedTask.result.interpretation.conclusion}</p>
                    )}
                    {selectedTask.result.interpretation.logic && (
                      <p className={textPrimary}><span className={`font-semibold ${textSecondary}`}>Logic: </span>{selectedTask.result.interpretation.logic}</p>
                    )}
                    {selectedTask.result.interpretation.guidance && (
                      <p className={textPrimary}><span className={`font-semibold ${textSecondary}`}>Guidance: </span>{selectedTask.result.interpretation.guidance}</p>
                    )}
                  </div>
                </div>
              )}

              {selectedTask.result?.report_url && (
                <a
                  href={getReportUrl(selectedTask.result.report_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-500 transition-colors shadow-sm"
                >
                  <ExternalLink className="h-4 w-4" />
                  View Full Report
                </a>
              )}

              {selectedTask.result?.params && (
                <div>
                  <p className={`text-xs font-medium uppercase tracking-wider mb-1.5 ${textMuted}`}>Parameters</p>
                  <p className={`text-xs font-mono tabular-nums ${textSecondary}`}>
                    {selectedTask.result.params.universe} · {selectedTask.result.params.start_date} ~ {selectedTask.result.params.end_date} · {selectedTask.result.params.n_groups}G · {selectedTask.result.params.holding_period}D hold · {selectedTask.result.params.stock_count} stocks
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
