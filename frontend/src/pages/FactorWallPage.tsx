import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Trophy, Loader2, ArrowRight, ChevronDown, ChevronUp,
  FlaskConical, BarChart3, Github,
} from "lucide-react";

interface WallFactor {
  id: string;
  expression: string;
  title?: string;
  description?: string;
  source?: string;
  metrics: {
    sharpe: number;
    cagr: number;
    max_drawdown: number;
    ic_mean: number;
    score?: number;
    grade?: string;
  };
  params: {
    universe: string;
    holding_period: number;
  };
}

const GRADE_STYLES: Record<string, { bg: string; text: string; ring: string }> = {
  A: { bg: "bg-emerald-50", text: "text-emerald-700", ring: "ring-emerald-200" },
  B: { bg: "bg-blue-50", text: "text-blue-700", ring: "ring-blue-200" },
  C: { bg: "bg-amber-50", text: "text-amber-700", ring: "ring-amber-200" },
  D: { bg: "bg-gray-50", text: "text-gray-500", ring: "ring-gray-200" },
};

const RANK_STYLES = [
  "bg-amber-400 text-white",
  "bg-gray-300 text-gray-700",
  "bg-amber-600 text-white",
];

function MetricCell({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="text-center">
      <div className="text-gray-400 mb-0.5">{label}</div>
      <div className={`font-bold ${positive === true ? "text-emerald-600" : positive === false ? "text-red-500" : "text-gray-700"}`}>
        {value}
      </div>
    </div>
  );
}

export default function FactorWallPage() {
  const navigate = useNavigate();
  const [factors, setFactors] = useState<WallFactor[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v1/factor-library/wall?limit=50")
      .then((res) => res.json())
      .then((data) => setFactors(data.factors ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggleExpand = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  return (
    <div className="min-h-screen bg-[#f9fafb]">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2.5">
            <FlaskConical className="h-6 w-6 text-blue-600" />
            <span className="text-lg font-bold text-gray-900">QuantGPT</span>
          </a>
          <div className="flex items-center gap-3">
            <a
              href="https://github.com/Miasyster/quantgpt"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
            >
              <Github className="h-4 w-4" />
              GitHub
            </a>
            <button
              onClick={() => navigate("/login")}
              className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              开始使用
            </button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <div className="bg-gradient-to-b from-white to-[#f9fafb] border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-6 py-12 text-center">
          <div className="flex items-center justify-center gap-2.5 mb-3">
            <Trophy className="h-8 w-8 text-amber-500" />
            <h1 className="text-2xl font-bold text-gray-900">因子排行榜</h1>
          </div>
          <p className="text-gray-500 max-w-lg mx-auto">
            社区精选 A 股量化因子，基于 Sharpe、IC、单调性等多维指标综合评分。
            <br />
            一键复刻回测，验证因子有效性。
          </p>
          <div className="flex items-center justify-center gap-6 mt-6 text-sm text-gray-400">
            <span className="flex items-center gap-1.5">
              <BarChart3 className="h-4 w-4" />
              {factors.length} 个精选因子
            </span>
            <span>沪深300 / 中证500 / 中证1000</span>
          </div>
        </div>
      </div>

      {/* Factor list */}
      <div className="max-w-5xl mx-auto px-6 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-24 text-gray-400">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            <span className="text-sm">加载因子榜...</span>
          </div>
        ) : factors.length === 0 ? (
          <div className="text-center py-20">
            <Trophy className="h-14 w-14 text-gray-200 mx-auto mb-4" />
            <p className="text-gray-500 text-lg font-medium mb-2">暂无精选因子</p>
            <p className="text-gray-400 text-sm mb-6">
              成为第一个上榜的研究者 — 回测你的因子表达式，投稿审核通过即上榜。
            </p>
            <button
              onClick={() => navigate("/login")}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              <FlaskConical className="h-4 w-4" />
              开始回测
            </button>
          </div>
        ) : (
          <div className="space-y-2.5">
            {factors.map((f, i) => {
              const m = f.metrics;
              const grade = m.grade || "C";
              const score = m.score ?? 0;
              const gs = GRADE_STYLES[grade] || GRADE_STYLES.D;
              const isExpanded = expandedId === f.id;
              const rankClass = i < 3 ? RANK_STYLES[i] : "bg-gray-100 text-gray-500";

              return (
                <div
                  key={f.id}
                  className="rounded-xl border border-gray-200 bg-white hover:shadow-md transition-all overflow-hidden"
                >
                  {/* Main row */}
                  <div className="flex items-center gap-4 px-5 py-4">
                    {/* Rank */}
                    <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${rankClass}`}>
                      {i + 1}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-semibold text-gray-900 truncate">
                          {f.title || f.expression.slice(0, 40)}
                        </span>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ring-1 ${gs.bg} ${gs.text} ${gs.ring}`}>
                          {grade}级
                          {score > 0 && <span className="font-normal opacity-75">{score.toFixed(0)}分</span>}
                        </span>
                        {f.source === "official" && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 font-medium">官方</span>
                        )}
                      </div>
                      <code className="text-xs font-mono text-blue-600 truncate block">
                        {f.expression}
                      </code>
                    </div>

                    {/* Metrics (desktop) */}
                    <div className="hidden md:flex items-center gap-5 text-xs shrink-0">
                      <MetricCell label="Sharpe" value={m.sharpe?.toFixed(2)} positive={m.sharpe >= 0.5 ? true : m.sharpe < 0 ? false : undefined} />
                      <MetricCell label="年化" value={`${(m.cagr * 100).toFixed(1)}%`} positive={m.cagr >= 0} />
                      <MetricCell label="回撤" value={`${(m.max_drawdown * 100).toFixed(1)}%`} positive={false} />
                      <MetricCell label="IC" value={(m.ic_mean ?? 0).toFixed(3)} positive={(m.ic_mean ?? 0) > 0.03 ? true : undefined} />
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => navigate("/login")}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-50 text-blue-600 text-xs font-medium hover:bg-blue-100 transition-colors"
                      >
                        复刻回测 <ArrowRight className="h-3 w-3" />
                      </button>
                      <button
                        onClick={() => toggleExpand(f.id)}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                      >
                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="px-5 pb-4 pt-0 border-t border-gray-100">
                      {f.description && (
                        <p className="text-sm text-gray-600 mt-3 leading-relaxed">{f.description}</p>
                      )}
                      {/* Mobile metrics */}
                      <div className="flex flex-wrap gap-4 mt-3 md:hidden text-xs">
                        <span>Sharpe <b className={m.sharpe >= 0.5 ? "text-emerald-600" : "text-gray-700"}>{m.sharpe?.toFixed(2)}</b></span>
                        <span>年化 <b className={m.cagr >= 0 ? "text-emerald-600" : "text-red-500"}>{(m.cagr * 100).toFixed(1)}%</b></span>
                        <span>回撤 <b className="text-red-500">{(m.max_drawdown * 100).toFixed(1)}%</b></span>
                        <span>IC <b>{(m.ic_mean ?? 0).toFixed(3)}</b></span>
                      </div>
                      <div className="flex items-center gap-3 mt-3 text-[11px] text-gray-400">
                        <span>{f.params?.universe || "hs300"}</span>
                        <span>{f.params?.holding_period || 5}日持仓</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* CTA */}
        {factors.length > 0 && (
          <div className="mt-10 rounded-xl border border-dashed border-blue-200 bg-blue-50/50 p-8 text-center">
            <Trophy className="h-8 w-8 text-blue-400 mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-gray-900 mb-1">你的因子也能上榜</h3>
            <p className="text-xs text-gray-500 mb-4">
              注册后回测你的因子表达式，点击"投稿因子墙"提交。审核通过即上榜，展示给所有用户。
            </p>
            <button
              onClick={() => navigate("/login")}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              <FlaskConical className="h-4 w-4" />
              免费注册，开始回测
            </button>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-200 mt-12">
        <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between text-xs text-gray-400">
          <span>QuantGPT — 自然语言驱动的 A 股因子回测工具</span>
          <a
            href="https://github.com/Miasyster/quantgpt"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 hover:text-gray-600 transition-colors"
          >
            <Github className="h-3.5 w-3.5" />
            开源项目
          </a>
        </div>
      </footer>
    </div>
  );
}
