import { useState, useEffect, useCallback } from "react";
import {
  Shield,
  LayoutDashboard,
  Users,
  ListTodo,
  MessageSquare,
  LogOut,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Loader2,
  UserRound,
  ClipboardList,
  TrendingUp,
  Activity,
  Inbox,
  AlertCircle,
  Clock,
  Play,
} from "lucide-react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Bar, Legend, Line, ComposedChart,
} from "recharts";
import {
  fetchOverview,
  fetchUsers,
  fetchTasks,
  fetchFeedbacks,
  resolveFeedback,
  fetchScheduledJobs,
  triggerJob,
  adminLogout,
} from "../api/admin";
import type { Overview, AdminUser, AdminTask, AdminFeedback, ScheduledJob } from "../api/admin";

type Tab = "overview" | "users" | "tasks" | "feedbacks" | "scheduled";

function formatTime(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
}

// ---- Pagination component ----
function Pagination({
  page,
  total,
  pageSize,
  onChange,
}: {
  page: number;
  total: number;
  pageSize: number;
  onChange: (p: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between mt-4 text-sm text-gray-600">
      <span>
        共 {total} 条，第 {page}/{totalPages} 页
      </span>
      <div className="flex gap-1">
        <button
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="px-2 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
          className="px-2 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ---- Status badge ----
function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    pending: "bg-yellow-100 text-yellow-700",
    iteration_completed: "bg-blue-100 text-blue-700",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || "bg-gray-100 text-gray-600"}`}
    >
      {status}
    </span>
  );
}

// ---- Overview Tab ----
function OverviewTab() {
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOverview()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );

  if (!data) return <div className="text-gray-500 py-8 text-center">加载失败</div>;

  const cards = [
    { label: "注册用户", value: data.user_count, color: "text-blue-600", bg: "bg-blue-50", icon: UserRound, iconColor: "text-blue-500" },
    { label: "总任务数", value: data.task_count, color: "text-indigo-600", bg: "bg-indigo-50", icon: ClipboardList, iconColor: "text-indigo-500" },
    { label: "成功率", value: `${data.success_rate}%`, color: "text-green-600", bg: "bg-green-50", icon: TrendingUp, iconColor: "text-green-500" },
    { label: "今日活跃", value: data.today_active, color: "text-amber-600", bg: "bg-amber-50", icon: Activity, iconColor: "text-amber-500" },
    { label: "总反馈数", value: data.feedback_count, color: "text-purple-600", bg: "bg-purple-50", icon: Inbox, iconColor: "text-purple-500" },
    { label: "未处理反馈", value: data.unresolved_feedback_count, color: "text-red-600", bg: "bg-red-50", icon: AlertCircle, iconColor: "text-red-500" },
  ];

  const PIE_COLORS: Record<string, string> = {
    completed: "#22c55e",
    failed: "#ef4444",
    pending: "#eab308",
    iteration_completed: "#3b82f6",
  };
  const PIE_FALLBACK = "#94a3b8";

  const successPct = data.success_rate;

  return (
    <div className="space-y-6">
      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-5 flex items-start gap-4">
              <div className={`${c.bg} rounded-lg p-2.5 shrink-0`}>
                <Icon className={`h-5 w-5 ${c.iconColor}`} />
              </div>
              <div>
                <div className="text-sm text-gray-500 mb-0.5">{c.label}</div>
                <div className={`text-2xl font-bold ${c.color}`}>{c.value}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Daily trend */}
        <div className="md:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-medium text-gray-700 mb-4">近 7 天任务趋势</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data.daily_tasks}>
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} width={30} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13 }}
                formatter={(v) => [String(v), "任务数"]}
              />
              <Area type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2} fill="url(#areaGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Right column: pie + ring */}
        <div className="flex flex-col gap-4">
          {/* Status pie */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 flex-1">
            <h3 className="text-sm font-medium text-gray-700 mb-2">任务状态分布</h3>
            {data.status_distribution.length > 0 ? (
              <ResponsiveContainer width="100%" height={130}>
                <PieChart>
                  <Pie
                    data={data.status_distribution}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={30}
                    outerRadius={55}
                    paddingAngle={2}
                  >
                    {data.status_distribution.map((entry) => (
                      <Cell key={entry.name} fill={PIE_COLORS[entry.name] || PIE_FALLBACK} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-gray-400 text-sm text-center py-8">暂无数据</div>
            )}
            <div className="flex flex-wrap gap-x-3 gap-y-1 justify-center mt-1">
              {data.status_distribution.map((s) => (
                <span key={s.name} className="flex items-center gap-1 text-xs text-gray-500">
                  <span
                    className="inline-block w-2 h-2 rounded-full"
                    style={{ backgroundColor: PIE_COLORS[s.name] || PIE_FALLBACK }}
                  />
                  {s.name}
                </span>
              ))}
            </div>
          </div>

          {/* Success rate ring */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 flex-1 flex flex-col items-center justify-center">
            <h3 className="text-sm font-medium text-gray-700 mb-2">成功率</h3>
            <div className="relative w-24 h-24">
              <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                <circle cx="18" cy="18" r="15.9" fill="none" stroke="#f3f4f6" strokeWidth="3" />
                <circle
                  cx="18"
                  cy="18"
                  r="15.9"
                  fill="none"
                  stroke="#22c55e"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeDasharray={`${successPct} ${100 - successPct}`}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold text-green-600">{successPct}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* User trend chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-medium text-gray-700 mb-4">用户增长趋势（近 30 天）</h3>
        {data.user_trend && data.user_trend.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={data.user_trend}>
              <defs>
                <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.8} />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.3} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "#9ca3af" }}
                axisLine={false}
                tickLine={false}
                interval={Math.floor(data.user_trend.length / 8)}
              />
              <YAxis
                yAxisId="left"
                allowDecimals={false}
                tick={{ fontSize: 12, fill: "#9ca3af" }}
                axisLine={false}
                tickLine={false}
                width={35}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                allowDecimals={false}
                tick={{ fontSize: 12, fill: "#9ca3af" }}
                axisLine={false}
                tickLine={false}
                width={35}
              />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13 }}
                formatter={(v, name) => [
                  String(v),
                  name === "new_users" ? "新增用户" : "累计用户",
                ]}
              />
              <Legend
                formatter={(value: string) => (value === "new_users" ? "新增用户" : "累计用户")}
                wrapperStyle={{ fontSize: 12 }}
              />
              <Bar yAxisId="left" dataKey="new_users" fill="url(#barGrad)" radius={[3, 3, 0, 0]} barSize={14} />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="total_users"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-gray-400 text-sm text-center py-8">暂无数据</div>
        )}
      </div>
    </div>
  );
}

// ---- Users Tab ----
function UsersTab() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  const load = useCallback((p: number) => {
    setLoading(true);
    fetchUsers(p, pageSize)
      .then((d) => {
        setUsers(d.users);
        setTotal(d.total);
        setPage(d.page);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(1);
  }, [load]);

  if (loading && users.length === 0)
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="py-2 px-3 font-medium">邮箱</th>
              <th className="py-2 px-3 font-medium">昵称</th>
              <th className="py-2 px-3 font-medium">任务数</th>
              <th className="py-2 px-3 font-medium">注册时间</th>
              <th className="py-2 px-3 font-medium">最后登录</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2.5 px-3 font-mono text-xs">{u.email}</td>
                <td className="py-2.5 px-3">{u.nickname || "-"}</td>
                <td className="py-2.5 px-3">{u.task_count}</td>
                <td className="py-2.5 px-3 text-gray-500 text-xs">{formatTime(u.created_at)}</td>
                <td className="py-2.5 px-3 text-gray-500 text-xs">{formatTime(u.last_login_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} total={total} pageSize={pageSize} onChange={load} />
    </div>
  );
}

// ---- Tasks Tab ----
function TasksTab() {
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const pageSize = 20;

  const load = useCallback(
    (p: number, status?: string, taskType?: string) => {
      setLoading(true);
      const s = status ?? statusFilter;
      const t = taskType ?? typeFilter;
      fetchTasks(p, pageSize, { status: s || undefined, task_type: t || undefined })
        .then((d) => {
          setTasks(d.tasks);
          setTotal(d.total);
          setPage(d.page);
        })
        .finally(() => setLoading(false));
    },
    [statusFilter, typeFilter],
  );

  useEffect(() => {
    load(1);
  }, [load]);

  const handleStatusChange = (val: string) => {
    setStatusFilter(val);
    load(1, val, typeFilter);
  };

  const handleTypeChange = (val: string) => {
    setTypeFilter(val);
    load(1, statusFilter, val);
  };

  const typeLabel = (t: string) => {
    switch (t) {
      case "backtest": return "单因子";
      case "iteration": return "迭代";
      case "composite": return "多因子组合";
      case "mcp_backtest": return "MCP 回测";
      case "mcp_score": return "MCP 评分";
      case "mcp_antioverfit": return "MCP 反过拟合";
      case "mcp_rolling": return "MCP 滚动验证";
      default: return t;
    }
  };

  return (
    <div>
      <div className="mb-3 flex gap-4 items-center">
        <div className="flex gap-2 items-center">
          <label className="text-sm text-gray-500">状态：</label>
          <select
            value={statusFilter}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">全部</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="pending">pending</option>
            <option value="iteration_completed">iteration_completed</option>
          </select>
        </div>
        <div className="flex gap-2 items-center">
          <label className="text-sm text-gray-500">类型：</label>
          <select
            value={typeFilter}
            onChange={(e) => handleTypeChange(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">全部</option>
            <option value="backtest">单因子</option>
            <option value="iteration">迭代</option>
            <option value="composite">多因子组合</option>
            <option value="mcp_backtest">MCP 回测</option>
            <option value="mcp_score">MCP 评分</option>
            <option value="mcp_antioverfit">MCP 反过拟合</option>
            <option value="mcp_rolling">MCP 滚动验证</option>
          </select>
        </div>
      </div>
      {loading && tasks.length === 0 ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-500">
                <th className="py-2 px-3 font-medium">ID</th>
                <th className="py-2 px-3 font-medium">用户</th>
                <th className="py-2 px-3 font-medium">类型</th>
                <th className="py-2 px-3 font-medium">表达式</th>
                <th className="py-2 px-3 font-medium">状态</th>
                <th className="py-2 px-3 font-medium">创建时间</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-2.5 px-3 font-mono text-xs">{t.id}</td>
                  <td className="py-2.5 px-3 text-xs">{t.user_email}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{typeLabel(t.task_type)}</td>
                  <td className="py-2.5 px-3 font-mono text-xs max-w-[300px] truncate" title={t.expression || ""}>
                    {t.expression || (t.error ? <span className="text-red-500">{t.error}</span> : "-")}
                  </td>
                  <td className="py-2.5 px-3">
                    <StatusBadge status={t.status} />
                  </td>
                  <td className="py-2.5 px-3 text-gray-500 text-xs">{formatTime(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination page={page} total={total} pageSize={pageSize} onChange={(p) => load(p)} />
    </div>
  );
}

// ---- Feedbacks Tab ----
function FeedbacksTab() {
  const [feedbacks, setFeedbacks] = useState<AdminFeedback[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState<string | null>(null);
  const pageSize = 20;

  const load = useCallback((p: number) => {
    setLoading(true);
    fetchFeedbacks(p, pageSize)
      .then((d) => {
        setFeedbacks(d.feedbacks);
        setTotal(d.total);
        setPage(d.page);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(1);
  }, [load]);

  const handleResolve = async (id: string) => {
    setResolving(id);
    try {
      await resolveFeedback(id);
      setFeedbacks((prev) =>
        prev.map((f) => (f.id === id ? { ...f, resolved: true, resolved_at: new Date().toISOString() } : f)),
      );
    } finally {
      setResolving(null);
    }
  };

  if (loading && feedbacks.length === 0)
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="py-2 px-3 font-medium">用户</th>
              <th className="py-2 px-3 font-medium">描述</th>
              <th className="py-2 px-3 font-medium">截图</th>
              <th className="py-2 px-3 font-medium">时间</th>
              <th className="py-2 px-3 font-medium">状态</th>
              <th className="py-2 px-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {feedbacks.map((f) => (
              <tr key={f.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2.5 px-3 text-xs">{f.user_email}</td>
                <td className="py-2.5 px-3 max-w-[300px] truncate text-xs" title={f.description}>
                  {f.description}
                </td>
                <td className="py-2.5 px-3 text-xs">
                  {f.screenshot_path ? (
                    <a
                      href={`/api/v1/feedback-screenshots/${f.screenshot_path.split("/").pop()?.replace(".png", "") ?? f.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      查看
                    </a>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="py-2.5 px-3 text-gray-500 text-xs">{formatTime(f.created_at)}</td>
                <td className="py-2.5 px-3">
                  {f.resolved ? (
                    <span className="inline-flex items-center gap-1 text-green-600 text-xs">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      已处理
                    </span>
                  ) : (
                    <span className="text-amber-600 text-xs">待处理</span>
                  )}
                </td>
                <td className="py-2.5 px-3">
                  {!f.resolved && (
                    <button
                      onClick={() => handleResolve(f.id)}
                      disabled={resolving === f.id}
                      className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
                    >
                      {resolving === f.id ? "处理中..." : "标记已处理"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} total={total} pageSize={pageSize} onChange={load} />
    </div>
  );
}

// ---- Scheduled Jobs Tab ----
function ScheduledJobsTab() {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    fetchScheduledJobs()
      .then((d) => setJobs(d.jobs))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleTrigger = async (jobId: string) => {
    setTriggering(jobId);
    setMsg(null);
    try {
      const res = await triggerJob(jobId);
      setMsg(res.message);
      setTimeout(load, 2000);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "触发失败");
    } finally {
      setTriggering(null);
    }
  };

  const statusBadge = (status: string | null) => {
    if (!status) return <span className="text-gray-400 text-xs">-</span>;
    const colors: Record<string, string> = {
      success: "bg-green-100 text-green-700",
      failed: "bg-red-100 text-red-700",
      running: "bg-blue-100 text-blue-700",
      skipped: "bg-yellow-100 text-yellow-700",
    };
    return (
      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || "bg-gray-100 text-gray-600"}`}>
        {status}
      </span>
    );
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;

  return (
    <div>
      {msg && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-blue-50 text-blue-700 text-sm border border-blue-100">{msg}</div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="py-2 px-3 font-medium">任务名称</th>
              <th className="py-2 px-3 font-medium">说明</th>
              <th className="py-2 px-3 font-medium">执行计划</th>
              <th className="py-2 px-3 font-medium">下次执行</th>
              <th className="py-2 px-3 font-medium">上次执行</th>
              <th className="py-2 px-3 font-medium">状态</th>
              <th className="py-2 px-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-3 px-3 font-medium text-gray-800">{j.name}</td>
                <td className="py-3 px-3 text-xs text-gray-500 max-w-[200px]">{j.description}</td>
                <td className="py-3 px-3 text-xs font-mono text-gray-600">{j.schedule}</td>
                <td className="py-3 px-3 text-xs text-gray-500">{j.next_run ? formatTime(j.next_run) : "-"}</td>
                <td className="py-3 px-3 text-xs text-gray-500">{j.last_run ? formatTime(j.last_run) : "从未运行"}</td>
                <td className="py-3 px-3">
                  {statusBadge(j.last_status)}
                  {j.last_error && (
                    <div className="text-xs text-red-500 mt-1 max-w-[150px] truncate" title={j.last_error}>{j.last_error}</div>
                  )}
                </td>
                <td className="py-3 px-3">
                  <button
                    onClick={() => handleTrigger(j.id)}
                    disabled={triggering === j.id}
                    className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
                  >
                    {triggering === j.id
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <Play className="h-3.5 w-3.5" />}
                    立即执行
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---- Main AdminPage ----
export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("overview");

  const tabs: { key: Tab; label: string; icon: typeof LayoutDashboard }[] = [
    { key: "overview", label: "总览", icon: LayoutDashboard },
    { key: "users", label: "用户", icon: Users },
    { key: "tasks", label: "任务", icon: ListTodo },
    { key: "feedbacks", label: "反馈", icon: MessageSquare },
    { key: "scheduled", label: "定时任务", icon: Clock },
  ];

  return (
    <div className="min-h-screen bg-[#f9fafb]">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-blue-600" />
          <span className="font-semibold text-gray-900">QuantGPT Admin</span>
        </div>
        <button
          onClick={adminLogout}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
        >
          <LogOut className="h-4 w-4" />
          退出
        </button>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-6">
        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white rounded-lg border border-gray-200 p-1 w-fit">
          {tabs.map((t) => {
            const Icon = t.icon;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  active ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Icon className="h-4 w-4" />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        {tab === "overview" && <OverviewTab />}
        {tab === "users" && <UsersTab />}
        {tab === "tasks" && <TasksTab />}
        {tab === "feedbacks" && <FeedbacksTab />}
        {tab === "scheduled" && <ScheduledJobsTab />}
      </div>
    </div>
  );
}
