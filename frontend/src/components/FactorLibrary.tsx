import { useState, useEffect, useCallback } from "react";
import { Star, Trash2, ExternalLink } from "lucide-react";
import type { SavedFactor } from "../api/factorLibrary";
import { fetchFactors, deleteFactor } from "../api/factorLibrary";
import { getReportUrl } from "../api/client";

function pct(n: number): string {
  return (n * 100).toFixed(1) + "%";
}

function FactorItem({
  factor,
  onDelete,
}: {
  factor: SavedFactor;
  onDelete: (id: string) => void;
}) {
  const m = factor.metrics;
  const bs = factor.backtest_summary as Record<string, number> | null;

  return (
    <div className="group rounded-lg border border-gray-150 bg-white px-3 py-2.5 hover:shadow-sm transition-shadow">
      {/* Expression — single line truncated */}
      <div className="flex items-center gap-2 min-w-0">
        <code className="text-xs text-blue-700 font-mono truncate flex-1" title={factor.expression}>
          {factor.expression}
        </code>
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          {factor.report_url && (
            <a
              href={getReportUrl(factor.report_url)}
              target="_blank"
              rel="noreferrer"
              className="p-1 rounded text-gray-400 hover:text-blue-600"
              title="查看报告"
            >
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); if (confirm("确定删除？")) onDelete(factor.id); }}
            className="p-1 rounded text-gray-400 hover:text-red-500"
            title="删除"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </div>

      {/* Compact metrics row */}
      {m && (
        <div className="flex items-center gap-2 mt-1.5 text-[11px] text-gray-500">
          <span>S <span className="text-gray-700 font-medium">{m.sharpe.toFixed(2)}</span></span>
          <span className="text-gray-200">|</span>
          <span className={m.cagr >= 0 ? "text-emerald-600" : "text-red-500"}>{pct(m.cagr)}</span>
          <span className="text-gray-200">|</span>
          <span className="text-red-500">{pct(m.max_drawdown)}</span>
          {bs && (
            <>
              <span className="text-gray-200">|</span>
              <span>M {(bs.monotonicity_score ?? 0).toFixed(1)}</span>
            </>
          )}
        </div>
      )}

      {/* Meta line */}
      <div className="flex items-center gap-2 mt-1 text-[10px] text-gray-400">
        {factor.params && (
          <span>{(factor.params as Record<string, string>).universe}</span>
        )}
        {factor.created_at && (
          <span>{new Date(factor.created_at).toLocaleDateString("zh-CN")}</span>
        )}
      </div>
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

  if (loading) {
    return <div className="text-center py-8 text-xs text-gray-400">加载中...</div>;
  }

  if (factors.length === 0) {
    return (
      <div className="text-center py-12">
        <Star className="h-8 w-8 text-gray-200 mx-auto mb-2" />
        <p className="text-xs text-gray-500">因子库为空</p>
        <p className="text-[10px] text-gray-400 mt-1">回测结果页点击「收藏」保存因子</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <p className="text-xs text-gray-400 px-1">{factors.length} 个因子</p>
      {factors.map((f) => (
        <FactorItem key={f.id} factor={f} onDelete={handleDelete} />
      ))}
    </div>
  );
}
