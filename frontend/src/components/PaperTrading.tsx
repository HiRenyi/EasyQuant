import { useState, useEffect, useCallback } from "react";
import { TrendingUp, Pause, Play, Square, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { useColorMode } from "../contexts/ColorModeContext";
import type { PaperStrategy, PaperOrder } from "../api/paper";
import { fetchPaperStrategies, fetchPaperStrategy, fetchPaperOrders, updatePaperStrategy } from "../api/paper";

function pct(n: number, digits = 2) {
  return (n * 100).toFixed(digits) + "%";
}

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

const UNIVERSE_LABELS: Record<string, string> = {
  hs300: "沪深300", csi500: "中证500", csi1000: "中证1000", small_scale: "蓝筹5只",
};

interface Props {
  onCreateFromBacktest?: (expression: string, params: object) => void;
}

export default function PaperTrading(_props: Props) {
  const { colorMode, isDark, positiveClass, negativeClass } = useColorMode();
  const [strategies, setStrategies] = useState<PaperStrategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PaperStrategy | null>(null);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await fetchPaperStrategies();
      setStrategies(list);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const expand = useCallback(async (id: string) => {
    if (expandedId === id) { setExpandedId(null); setDetail(null); return; }
    setExpandedId(id);
    setLoadingDetail(true);
    try {
      const [d, o] = await Promise.all([fetchPaperStrategy(id), fetchPaperOrders(id)]);
      setDetail(d);
      setOrders(o.orders);
    } catch { /* ignore */ }
    finally { setLoadingDetail(false); }
  }, [expandedId]);

  const updateStatus = useCallback(async (id: string, status: string) => {
    try {
      const updated = await updatePaperStrategy(id, status);
      setStrategies((prev) => prev.map((s) => s.id === id ? { ...s, status: updated.status } : s));
    } catch (e) {
      alert(e instanceof Error ? e.message : "操作失败");
    }
  }, []);

  if (loading) return <div className="text-center py-16 text-sm text-gray-400">加载中...</div>;

  if (strategies.length === 0) {
    return (
      <div className="text-center py-20">
        <TrendingUp className="h-12 w-12 text-gray-200 mx-auto mb-4" />
        <p className="text-sm text-gray-500 mb-1">还没有模拟盘策略</p>
        <p className="text-xs text-gray-400">在回测结果页点击"上模拟盘"即可创建</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className={`text-sm font-semibold ${isDark ? "text-gray-300" : "text-gray-700"}`}>我的模拟盘 ({strategies.length})</h2>
        <button onClick={load} className={`p-1.5 rounded-lg text-gray-400 ${isDark ? "hover:bg-gray-800" : "hover:bg-gray-100"}`}>
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {strategies.map((s) => {
        const isExpanded = expandedId === s.id;
        const isUp = s.total_return >= 0;

        return (
          <div key={s.id} className={`rounded-xl border ${isDark ? "border-gray-700" : "border-gray-200"} ${isDark ? "bg-gray-900" : "bg-white"} overflow-hidden`}>
            {/* Header row */}
            <div
              className={`flex items-center gap-3 p-4 cursor-pointer ${isDark ? "hover:bg-gray-800" : "hover:bg-gray-50"}`}
              onClick={() => expand(s.id)}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${isDark ? "text-gray-200" : "text-gray-800"} truncate`}>{s.name}</span>
                  <StatusBadge status={s.status} />
                </div>
                <code className={`text-[11px] ${isDark ? "text-amber-400" : "text-blue-600"} font-mono truncate block mt-0.5`}>{s.expression}</code>
              </div>

              <div className="text-right shrink-0">
                <div className={`text-lg font-bold ${isUp ? positiveClass : negativeClass}`}>
                  {isUp ? "+" : ""}{pct(s.total_return)}
                </div>
                <div className="text-xs text-gray-400">¥{fmt(s.current_value)}</div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                {s.status === "active" && (
                  <button
                    onClick={(e) => { e.stopPropagation(); updateStatus(s.id, "paused"); }}
                    className={`p-1.5 rounded-lg text-gray-400 ${isDark ? "hover:bg-amber-500/10 hover:text-amber-400" : "hover:bg-amber-50 hover:text-amber-600"}`}
                    title="暂停"
                  >
                    <Pause className="h-3.5 w-3.5" />
                  </button>
                )}
                {s.status === "paused" && (
                  <button
                    onClick={(e) => { e.stopPropagation(); updateStatus(s.id, "active"); }}
                    className={`p-1.5 rounded-lg text-gray-400 ${isDark ? "hover:bg-emerald-500/10 hover:text-emerald-400" : "hover:bg-emerald-50 hover:text-emerald-600"}`}
                    title="恢复"
                  >
                    <Play className="h-3.5 w-3.5" />
                  </button>
                )}
                {s.status !== "stopped" && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("确定停止该策略？停止后无法恢复。")) updateStatus(s.id, "stopped");
                    }}
                    className={`p-1.5 rounded-lg text-gray-400 ${isDark ? "hover:bg-red-500/10 hover:text-red-400" : "hover:bg-red-50 hover:text-red-500"}`}
                    title="停止"
                  >
                    <Square className="h-3.5 w-3.5" />
                  </button>
                )}
                {isExpanded ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
              </div>
            </div>

            {/* Meta row */}
            <div className={`px-4 pb-3 flex gap-4 text-xs text-gray-400 border-t ${isDark ? "border-gray-700" : "border-gray-50"}`}>
              <span>{UNIVERSE_LABELS[s.universe] ?? s.universe}</span>
              <span>换仓 {s.holding_period} 天</span>
              <span>初始 ¥{fmt(s.initial_capital)}</span>
              {s.last_rebalance_date && <span>上次换仓 {s.last_rebalance_date}</span>}
              {s.next_rebalance_date && s.status === "active" && <span>下次换仓 {s.next_rebalance_date}</span>}
            </div>

            {/* Expanded detail */}
            {isExpanded && (
              <div className={`border-t ${isDark ? "border-gray-700" : "border-gray-100"} p-4 space-y-4 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
                {loadingDetail ? (
                  <div className="text-center py-4 text-xs text-gray-400">加载中...</div>
                ) : (
                  <>
                    {/* NAV curve */}
                    {detail?.nav_curve && detail.nav_curve.length > 0 && (
                      <NavChart data={detail.nav_curve} initialCapital={s.initial_capital} />
                    )}

                    {/* Orders */}
                    {orders.length > 0 && (
                      <div>
                        <p className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-600"} mb-2`}>最近交易记录</p>
                        <div className={`rounded-lg border ${isDark ? "border-gray-700" : "border-gray-200"} overflow-hidden ${isDark ? "bg-gray-900" : "bg-white"}`}>
                          <table className="w-full text-xs">
                            <thead>
                              <tr className={`${isDark ? "bg-gray-800" : "bg-gray-50"} ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                                <th className="px-3 py-2 text-left">日期</th>
                                <th className="px-3 py-2 text-left">股票</th>
                                <th className="px-3 py-2 text-left">方向</th>
                                <th className="px-3 py-2 text-right">股数</th>
                                <th className="px-3 py-2 text-right">价格</th>
                                <th className="px-3 py-2 text-right">金额</th>
                              </tr>
                            </thead>
                            <tbody>
                              {orders.slice(0, 20).map((o) => (
                                <tr key={o.id} className={`border-t ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                                  <td className={`px-3 py-1.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>{o.date}</td>
                                  <td className={`px-3 py-1.5 font-mono ${isDark ? "text-gray-300" : "text-gray-700"}`}>{o.stock_code}</td>
                                  <td className="px-3 py-1.5">
                                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                      o.direction === "buy"
                                        ? (colorMode === "cn"
                                            ? (isDark ? "bg-red-500/10 text-red-400" : "bg-red-50 text-red-700")
                                            : (isDark ? "bg-emerald-500/10 text-emerald-400" : "bg-emerald-50 text-emerald-700"))
                                        : (colorMode === "cn"
                                            ? (isDark ? "bg-emerald-500/10 text-emerald-400" : "bg-emerald-50 text-emerald-600")
                                            : (isDark ? "bg-red-500/10 text-red-400" : "bg-red-50 text-red-600"))
                                    }`}>
                                      {o.direction === "buy" ? "买入" : "卖出"}
                                    </span>
                                  </td>
                                  <td className={`px-3 py-1.5 text-right ${isDark ? "text-gray-400" : "text-gray-600"}`}>{o.shares}</td>
                                  <td className={`px-3 py-1.5 text-right ${isDark ? "text-gray-400" : "text-gray-600"}`}>{o.price.toFixed(2)}</td>
                                  <td className={`px-3 py-1.5 text-right ${isDark ? "text-gray-400" : "text-gray-600"}`}>¥{fmt(o.amount)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {orders.length === 0 && (
                      <p className="text-xs text-gray-400 text-center py-2">暂无交易记录，等待首次换仓</p>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const { isDark } = useColorMode();
  const map: Record<string, string> = {
    active: isDark ? "bg-emerald-500/10 text-emerald-400" : "bg-emerald-50 text-emerald-700",
    paused: isDark ? "bg-amber-500/10 text-amber-400" : "bg-amber-50 text-amber-700",
    stopped: isDark ? "bg-gray-800 text-gray-400" : "bg-gray-100 text-gray-500",
  };
  const fallback = isDark ? "bg-gray-800 text-gray-400" : "bg-gray-100 text-gray-500";
  const labels: Record<string, string> = { active: "运行中", paused: "已暂停", stopped: "已停止" };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${map[status] ?? fallback}`}>
      {labels[status] ?? status}
    </span>
  );
}

function NavChart({ data, initialCapital }: {
  data: { date: string; value: number; daily_return: number | null }[];
  initialCapital: number;
}) {
  const { isDark } = useColorMode();
  if (data.length < 2) return null;

  const values = data.map((d) => d.value);
  const min = Math.min(...values) * 0.995;
  const max = Math.max(...values) * 1.005;
  const range = max - min || 1;

  const W = 600;
  const H = 80;
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - ((d.value - min) / range) * H;
    return `${x},${y}`;
  }).join(" ");

  const isUp = data[data.length - 1].value >= initialCapital;
  const color = isUp ? "#10b981" : "#ef4444";

  return (
    <div>
      <p className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-600"} mb-2`}>净值曲线</p>
      <div className={`rounded-lg border ${isDark ? "border-gray-700" : "border-gray-200"} ${isDark ? "bg-gray-900" : "bg-white"} p-3`}>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-16" preserveAspectRatio="none">
          <polyline points={points} fill="none" stroke={color} strokeWidth="2" />
        </svg>
        <div className="flex justify-between text-[10px] text-gray-400 mt-1">
          <span>{data[0].date}</span>
          <span>{data[data.length - 1].date}</span>
        </div>
      </div>
    </div>
  );
}
