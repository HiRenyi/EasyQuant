import type { FactorInterpretation } from "../types/backtest";
import { Lightbulb, TrendingUp, BookOpen, AlertTriangle, Star, CheckCircle } from "lucide-react";

interface Props {
  interpretation: FactorInterpretation;
}

const SECTIONS = [
  { key: "logic", icon: BookOpen, label: "因子逻辑", color: "text-blue-600", bg: "bg-blue-50" },
  { key: "source", icon: TrendingUp, label: "收益来源", color: "text-emerald-600", bg: "bg-emerald-50" },
  { key: "guidance", icon: Lightbulb, label: "交易指导", color: "text-amber-600", bg: "bg-amber-50" },
  { key: "risk", icon: AlertTriangle, label: "失效风险", color: "text-red-500", bg: "bg-red-50" },
] as const;

const RATING_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  A: { bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-700", label: "强烈推荐" },
  B: { bg: "bg-blue-50 border-blue-200", text: "text-blue-700", label: "推荐" },
  C: { bg: "bg-amber-50 border-amber-200", text: "text-amber-700", label: "谨慎使用" },
  D: { bg: "bg-red-50 border-red-200", text: "text-red-600", label: "不推荐" },
};

export default function FactorInterpretationCard({ interpretation }: Props) {
  const rating = interpretation.rating?.toUpperCase();
  const ratingStyle = rating ? RATING_STYLES[rating] : null;

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-amber-500" />
        <h3 className="text-sm font-medium text-gray-700">AI 因子研报</h3>
        <span className="text-xs text-gray-400 ml-auto">仅供研究参考，不构成投资建议</span>
      </div>

      {/* Rating badge + conclusion */}
      {(ratingStyle || interpretation.conclusion) && (
        <div className="px-4 py-3 border-b border-gray-50 flex items-start gap-3">
          {ratingStyle && (
            <div className={`shrink-0 px-3 py-1.5 rounded-lg border ${ratingStyle.bg} flex items-center gap-1.5`}>
              <Star className={`h-4 w-4 ${ratingStyle.text}`} />
              <span className={`text-lg font-bold ${ratingStyle.text}`}>{rating}</span>
              <span className={`text-xs ${ratingStyle.text}`}>{ratingStyle.label}</span>
            </div>
          )}
          <div className="flex-1 min-w-0">
            {interpretation.conclusion && (
              <p className="text-sm text-gray-700 leading-relaxed">{interpretation.conclusion}</p>
            )}
            {interpretation.rating_reason && (
              <p className="text-xs text-gray-400 mt-1">{interpretation.rating_reason}</p>
            )}
          </div>
        </div>
      )}

      {/* Core sections */}
      <div className="divide-y divide-gray-50">
        {SECTIONS.map(({ key, icon: Icon, label, color, bg }) => {
          const text = interpretation[key];
          if (!text) return null;
          return (
            <div key={key} className="px-4 py-3 flex gap-3">
              <div className={`mt-0.5 p-1.5 rounded-lg ${bg} shrink-0`}>
                <Icon className={`h-3.5 w-3.5 ${color}`} />
              </div>
              <div>
                <p className={`text-xs font-medium ${color} mb-1`}>{label}</p>
                <p className="text-sm text-gray-600 leading-relaxed">{text}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Suggestions */}
      {interpretation.suggestions && interpretation.suggestions.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-100 bg-gray-50/50">
          <p className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
            <CheckCircle className="h-3 w-3" />
            改进建议
          </p>
          <ul className="space-y-1">
            {interpretation.suggestions.map((s, i) => (
              <li key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                <span className="text-gray-300 mt-0.5 shrink-0">{i + 1}.</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
