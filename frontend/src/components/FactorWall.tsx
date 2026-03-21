import { useState, useEffect } from "react";
import { TrendingUp, Loader2, Trophy, ArrowRight } from "lucide-react";

interface WallFactor {
  expression: string;
  title?: string;
  description?: string;
  source?: string;
  metrics: {
    sharpe: number;
    cagr: number;
    max_drawdown: number;
    ic_mean: number;
  };
  params: {
    universe: string;
    holding_period: number;
  };
}

interface Props {
  onTryFactor?: (expression: string) => void;
}

export default function FactorWall({ onTryFactor }: Props) {
  const [factors, setFactors] = useState<WallFactor[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/factor-library/wall?limit=12")
      .then((res) => res.json())
      .then((data) => setFactors(data.factors ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-400">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  if (factors.length === 0) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <Trophy className="h-5 w-5 text-amber-500" />
        <h2 className="text-sm font-semibold text-gray-900">精选高分因子</h2>
        <span className="text-xs text-gray-400">来自社区用户的优质因子策略</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {factors.map((f, i) => {
          const m = f.metrics;
          return (
            <div
              key={i}
              className="group rounded-lg border border-gray-200 bg-white p-3.5 hover:shadow-md hover:border-blue-200 transition-all"
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                {f.title && f.title !== f.expression.slice(0, 60) ? (
                  <span className="text-xs font-medium text-gray-800 line-clamp-1">{f.title}</span>
                ) : null}
                {f.source === "official" && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 shrink-0">官方</span>
                )}
              </div>
              <code className="text-xs font-mono text-blue-700 line-clamp-2 leading-relaxed block mb-2.5">
                {f.expression}
              </code>
              <div className="flex items-center gap-3 text-[11px]">
                <span className="flex items-center gap-1">
                  <TrendingUp className="h-3 w-3 text-emerald-500" />
                  <span className="text-gray-500">Sharpe</span>
                  <span className="font-semibold text-gray-800">{m.sharpe?.toFixed(2)}</span>
                </span>
                <span className={`font-medium ${m.cagr >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                  {(m.cagr * 100).toFixed(1)}%
                </span>
                <span className="text-red-400 text-[10px]">
                  DD {(m.max_drawdown * 100).toFixed(1)}%
                </span>
              </div>
              {onTryFactor && (
                <button
                  onClick={() => onTryFactor(f.expression)}
                  className="mt-2.5 w-full flex items-center justify-center gap-1 text-xs text-blue-600 hover:text-blue-700 py-1.5 rounded-md hover:bg-blue-50 transition-colors opacity-0 group-hover:opacity-100"
                >
                  一键回测 <ArrowRight className="h-3 w-3" />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
