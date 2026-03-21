import type { FactorInterpretation } from "../types/backtest";
import { Lightbulb, TrendingUp, BookOpen, AlertTriangle } from "lucide-react";

interface Props {
  interpretation: FactorInterpretation;
}

const SECTIONS = [
  { key: "logic", icon: BookOpen, label: "因子逻辑", color: "text-blue-600", bg: "bg-blue-50" },
  { key: "source", icon: TrendingUp, label: "收益来源", color: "text-emerald-600", bg: "bg-emerald-50" },
  { key: "guidance", icon: Lightbulb, label: "交易指导", color: "text-amber-600", bg: "bg-amber-50" },
  { key: "risk", icon: AlertTriangle, label: "失效风险", color: "text-red-500", bg: "bg-red-50" },
] as const;

export default function FactorInterpretationCard({ interpretation }: Props) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-amber-500" />
        <h3 className="text-sm font-medium text-gray-700">AI 因子解读</h3>
        <span className="text-xs text-gray-400 ml-auto">仅供研究参考，不构成投资建议</span>
      </div>
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
    </div>
  );
}
