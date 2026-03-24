import { useState, useEffect, useCallback } from "react";
import { Trophy, Loader2, ArrowRight, Send, ChevronDown, ChevronUp } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useColorMode } from "../contexts/ColorModeContext";

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

interface Props {
  onTryFactor?: (expression: string) => void;
}

const getGradeStyles = (isDark: boolean): Record<string, { bg: string; text: string; ring: string }> => ({
  A: {
    bg: isDark ? "bg-emerald-500/10" : "bg-emerald-50",
    text: isDark ? "text-emerald-400" : "text-emerald-700",
    ring: "ring-emerald-200",
  },
  B: {
    bg: isDark ? "bg-amber-500/10" : "bg-blue-50",
    text: isDark ? "text-amber-400" : "text-blue-700",
    ring: "ring-blue-200",
  },
  C: {
    bg: isDark ? "bg-amber-500/10" : "bg-amber-50",
    text: isDark ? "text-amber-400" : "text-amber-700",
    ring: "ring-amber-200",
  },
  D: {
    bg: isDark ? "bg-gray-800" : "bg-gray-50",
    text: isDark ? "text-gray-400" : "text-gray-500",
    ring: isDark ? "ring-gray-700" : "ring-gray-200",
  },
});

const RANK_STYLES = [
  "bg-amber-400 text-white",    // #1
  "bg-gray-300 text-gray-700",  // #2
  "bg-amber-600 text-white",    // #3
];

export default function FactorWall({ onTryFactor }: Props) {
  const { isGuest, user } = useAuth();
  const { isDark, positiveClass, negativeClass } = useColorMode();
  const GRADE_STYLES = getGradeStyles(isDark);
  const [factors, setFactors] = useState<WallFactor[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/v1/factor-library/wall?limit=20`)
      .then((res) => res.json())
      .then((data) => setFactors(data.factors ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggleExpand = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-gray-400">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span className="text-sm">加载因子榜...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2.5 mb-1.5">
            <Trophy className="h-6 w-6 text-amber-500" />
            <h2 className={`text-lg font-bold ${isDark ? "text-gray-100" : "text-gray-900"}`}>因子排行榜</h2>
          </div>
          <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>
            社区精选高分因子，一键复刻回测验证。评分基于 Sharpe、单调性、IC 等综合指标。
          </p>
        </div>
        {!isGuest && user && (
          <a
            href="#submit"
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-colors shrink-0"
          >
            <Send className="h-3.5 w-3.5" />
            投稿上榜
          </a>
        )}
      </div>

      {factors.length === 0 ? (
        <div className="text-center py-16">
          <Trophy className="h-12 w-12 text-gray-200 mx-auto mb-3" />
          <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>暂无精选因子</p>
          <p className="text-xs text-gray-400 mt-1">回测后点击"投稿因子墙"，审核通过即上榜</p>
        </div>
      ) : (
        <div className="space-y-2">
          {factors.map((f, i) => {
            const m = f.metrics;
            const grade = m.grade || "C";
            const score = m.score ?? 0;
            const gs = GRADE_STYLES[grade] || GRADE_STYLES.D;
            const isExpanded = expandedId === f.id;
            const rankClass = i < 3 ? RANK_STYLES[i] : (isDark ? "bg-gray-800 text-gray-400" : "bg-gray-100 text-gray-500");

            return (
              <div
                key={f.id}
                className={`rounded-xl border ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"} hover:shadow-md transition-all overflow-hidden`}
              >
                {/* Main row */}
                <div className="flex items-center gap-4 px-4 py-3.5">
                  {/* Rank */}
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${rankClass}`}>
                    {i + 1}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-sm font-semibold ${isDark ? "text-gray-100" : "text-gray-900"} truncate`}>
                        {f.title || f.expression.slice(0, 40)}
                      </span>
                      {/* Grade badge */}
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ring-1 ${gs.bg} ${gs.text} ${gs.ring}`}>
                        {grade}级
                        {score > 0 && <span className="font-normal opacity-75">{score.toFixed(0)}分</span>}
                      </span>
                      {f.source === "official" && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${isDark ? "bg-amber-500/10 text-amber-400" : "bg-amber-50 text-amber-600"} font-medium`}>官方</span>
                      )}
                    </div>
                    <code className={`text-xs font-mono ${isDark ? "text-amber-400" : "text-blue-600"} truncate block`}>
                      {f.expression}
                    </code>
                  </div>

                  {/* Metrics */}
                  <div className="hidden sm:flex items-center gap-4 text-xs shrink-0">
                    <div className="text-center">
                      <div className="text-gray-400 mb-0.5">Sharpe</div>
                      <div className={`font-bold ${m.sharpe >= 0.5 ? positiveClass : m.sharpe >= 0 ? (isDark ? "text-gray-300" : "text-gray-700") : negativeClass}`}>
                        {m.sharpe?.toFixed(2)}
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-gray-400 mb-0.5">年化</div>
                      <div className={`font-bold ${m.cagr >= 0 ? positiveClass : negativeClass}`}>
                        {(m.cagr * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-gray-400 mb-0.5">回撤</div>
                      <div className={`font-bold ${negativeClass}`}>
                        {(m.max_drawdown * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-gray-400 mb-0.5">IC</div>
                      <div className={`font-bold ${(m.ic_mean ?? 0) > 0.03 ? positiveClass : (isDark ? "text-gray-300" : "text-gray-700")}`}>
                        {(m.ic_mean ?? 0).toFixed(3)}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    {onTryFactor && (
                      <button
                        onClick={() => onTryFactor(f.expression)}
                        className={`flex items-center gap-1 px-3 py-1.5 rounded-lg ${isDark ? "bg-amber-500/10 text-amber-400" : "bg-blue-50 text-blue-600"} text-xs font-medium hover:bg-blue-100 transition-colors`}
                      >
                        复刻回测 <ArrowRight className="h-3 w-3" />
                      </button>
                    )}
                    <button
                      onClick={() => toggleExpand(f.id)}
                      className={`p-1.5 rounded-lg text-gray-400 hover:text-gray-600 ${isDark ? "hover:bg-gray-800" : "hover:bg-gray-100"} transition-colors`}
                    >
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                {/* Expanded: description + mobile metrics */}
                {isExpanded && (
                  <div className={`px-4 pb-4 pt-0 border-t ${isDark ? "border-gray-700" : "border-gray-100"}`}>
                    {f.description && (
                      <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-600"} mt-3 leading-relaxed`}>{f.description}</p>
                    )}
                    {/* Mobile metrics */}
                    <div className="flex flex-wrap gap-3 mt-3 sm:hidden text-xs">
                      <span>Sharpe <b className={m.sharpe >= 0.5 ? positiveClass : (isDark ? "text-gray-300" : "text-gray-700")}>{m.sharpe?.toFixed(2)}</b></span>
                      <span>年化 <b className={m.cagr >= 0 ? positiveClass : negativeClass}>{(m.cagr * 100).toFixed(1)}%</b></span>
                      <span>回撤 <b className={negativeClass}>{(m.max_drawdown * 100).toFixed(1)}%</b></span>
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

      {/* Submit section */}
      {!isGuest && user && (
        <div id="submit" className={`rounded-xl border border-dashed ${isDark ? "border-amber-500/30 bg-amber-500/5" : "border-blue-200 bg-blue-50/50"} p-6 text-center`}>
          <Trophy className="h-8 w-8 text-blue-400 mx-auto mb-2" />
          <h3 className={`text-sm font-semibold ${isDark ? "text-gray-100" : "text-gray-900"} mb-1`}>我的因子也要上榜</h3>
          <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"} mb-3`}>
            回测完成后，在结果页点击「投稿因子墙」按钮提交你的因子。<br/>
            审核通过后即可上榜，展示给所有用户。
          </p>
        </div>
      )}
    </div>
  );
}
