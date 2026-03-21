import { useState, useEffect, useCallback } from "react";
import { Star, Trash2, ExternalLink, Edit3, Check, X, ChevronDown, ChevronUp } from "lucide-react";
import type { SavedFactor } from "../api/factorLibrary";
import { fetchFactors, deleteFactor, updateFactor } from "../api/factorLibrary";
import { getReportUrl } from "../api/client";

function pct(n: number): string {
  return (n * 100).toFixed(2) + "%";
}

function num(n: number): string {
  return n.toFixed(4);
}

function MetricBadge({ label, value, color }: { label: string; value: string; color?: string }) {
  const colorClass =
    color === "green"
      ? "text-emerald-700 bg-emerald-50"
      : color === "red"
        ? "text-red-700 bg-red-50"
        : "text-gray-700 bg-gray-50";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
      <span className="text-gray-400">{label}</span> {value}
    </span>
  );
}

function FactorCard({
  factor,
  onDelete,
  onUpdate,
}: {
  factor: SavedFactor;
  onDelete: (id: string) => void;
  onUpdate: (id: string, updates: { name?: string; note?: string }) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(factor.name || "");
  const [editNote, setEditNote] = useState(factor.note || "");

  const m = factor.metrics;
  const bs = factor.backtest_summary as Record<string, number> | null;

  const commitEdit = () => {
    onUpdate(factor.id, { name: editName.trim() || undefined, note: editNote.trim() || undefined });
    setEditing(false);
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden transition-shadow hover:shadow-sm">
      {/* Header */}
      <div className="px-4 py-3 flex items-start gap-3">
        <Star className="h-4 w-4 text-amber-400 mt-0.5 shrink-0 fill-amber-400" />
        <div className="flex-1 min-w-0">
          {editing ? (
            <div className="space-y-2">
              <input
                className="w-full border border-gray-300 rounded-lg px-2.5 py-1.5 text-sm outline-none focus:border-blue-400"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                placeholder="因子名称"
                autoFocus
              />
              <textarea
                className="w-full border border-gray-300 rounded-lg px-2.5 py-1.5 text-sm outline-none focus:border-blue-400 resize-none"
                rows={2}
                value={editNote}
                onChange={(e) => setEditNote(e.target.value)}
                placeholder="添加备注..."
              />
              <div className="flex gap-2">
                <button onClick={commitEdit} className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1">
                  <Check className="h-3 w-3" /> 保存
                </button>
                <button onClick={() => setEditing(false)} className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1">
                  <X className="h-3 w-3" /> 取消
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-medium text-gray-900 truncate">{factor.name || factor.expression.slice(0, 40)}</h4>
                <button onClick={() => { setEditName(factor.name || ""); setEditNote(factor.note || ""); setEditing(true); }} className="opacity-0 group-hover:opacity-100 p-0.5">
                  <Edit3 className="h-3 w-3 text-gray-400 hover:text-gray-600" />
                </button>
              </div>
              {factor.note && <p className="text-xs text-gray-500 mt-0.5">{factor.note}</p>}
            </>
          )}
          <code className="text-xs text-blue-600 font-mono break-all leading-relaxed mt-1 block">{factor.expression}</code>

          {/* Quick metrics */}
          {m && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              <MetricBadge label="Sharpe" value={num(m.sharpe)} color={m.sharpe >= 1 ? "green" : undefined} />
              <MetricBadge label="年化" value={pct(m.cagr)} color={m.cagr >= 0 ? "green" : "red"} />
              <MetricBadge label="回撤" value={pct(m.max_drawdown)} color="red" />
              {bs && <MetricBadge label="单调性" value={num(bs.monotonicity_score ?? 0)} color={(bs.monotonicity_score ?? 0) >= 0.8 ? "green" : undefined} />}
              {bs && <MetricBadge label="IC" value={num(bs.ic_mean ?? 0)} />}
            </div>
          )}

          {/* Meta */}
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
            {factor.params && <span>{(factor.params as Record<string, string>).universe} · {(factor.params as Record<string, string>).start_date}~{(factor.params as Record<string, string>).end_date}</span>}
            {factor.created_at && <span>{new Date(factor.created_at).toLocaleDateString("zh-CN")}</span>}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          {factor.report_url && (
            <a
              href={getReportUrl(factor.report_url)}
              target="_blank"
              rel="noreferrer"
              className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
              title="查看报告"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            title="展开详情"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          <button
            onClick={() => { if (confirm("确定删除这个因子？")) onDelete(factor.id); }}
            className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
            title="删除"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && m && (
        <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/50">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-y-2 gap-x-4 text-xs">
            <div><span className="text-gray-400">总收益</span> <span className={m.total_return >= 0 ? "text-emerald-600" : "text-red-600"}>{pct(m.total_return)}</span></div>
            <div><span className="text-gray-400">年化收益</span> <span className={m.cagr >= 0 ? "text-emerald-600" : "text-red-600"}>{pct(m.cagr)}</span></div>
            <div><span className="text-gray-400">Sharpe</span> <span className="font-medium">{num(m.sharpe)}</span></div>
            <div><span className="text-gray-400">Sortino</span> <span className="font-medium">{num(m.sortino)}</span></div>
            <div><span className="text-gray-400">最大回撤</span> <span className="text-red-600">{pct(m.max_drawdown)}</span></div>
            <div><span className="text-gray-400">波动率</span> <span>{pct(m.volatility)}</span></div>
            <div><span className="text-gray-400">胜率</span> <span>{pct(m.win_rate)}</span></div>
            <div><span className="text-gray-400">盈亏比</span> <span>{num(m.profit_factor)}</span></div>
            {bs && (
              <>
                <div><span className="text-gray-400">单调性</span> <span className="font-medium">{num(bs.monotonicity_score ?? 0)}</span></div>
                <div><span className="text-gray-400">IC均值</span> <span>{num(bs.ic_mean ?? 0)}</span></div>
                <div><span className="text-gray-400">Rank IC</span> <span>{num(bs.rank_ic_mean ?? 0)}</span></div>
                <div><span className="text-gray-400">IC胜率</span> <span>{pct(bs.ic_win_rate ?? 0)}</span></div>
                <div><span className="text-gray-400">换手率</span> <span>{pct(bs.turnover ?? 0)}</span></div>
                <div><span className="text-gray-400">多空Sharpe</span> <span>{num(bs.long_short_sharpe ?? 0)}</span></div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function FactorLibrary() {
  const [factors, setFactors] = useState<SavedFactor[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchFactors();
      setFactors(data);
    } catch (e) {
      console.error("Failed to load factors:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (id: string) => {
    try {
      await deleteFactor(id);
      setFactors((prev) => prev.filter((f) => f.id !== id));
    } catch (e) {
      alert("删除失败: " + (e instanceof Error ? e.message : "未知错误"));
    }
  };

  const handleUpdate = async (id: string, updates: { name?: string; note?: string }) => {
    try {
      const updated = await updateFactor(id, updates);
      setFactors((prev) => prev.map((f) => (f.id === id ? updated : f)));
    } catch (e) {
      alert("更新失败: " + (e instanceof Error ? e.message : "未知错误"));
    }
  };

  if (loading) {
    return (
      <div className="text-center py-12 text-sm text-gray-400">加载中...</div>
    );
  }

  if (factors.length === 0) {
    return (
      <div className="text-center py-16">
        <Star className="h-10 w-10 text-gray-200 mx-auto mb-3" />
        <p className="text-sm text-gray-500">因子库为空</p>
        <p className="text-xs text-gray-400 mt-1">在回测结果页点击「收藏因子」将好的因子保存到这里</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">我的因子库 ({factors.length})</h3>
      </div>
      {factors.map((f) => (
        <FactorCard key={f.id} factor={f} onDelete={handleDelete} onUpdate={handleUpdate} />
      ))}
    </div>
  );
}
