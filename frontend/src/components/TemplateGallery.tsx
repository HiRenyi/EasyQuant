import { useState, useEffect } from "react";
import { Zap, TrendingUp, BarChart3, Activity, LineChart, Layers, ChevronRight } from "lucide-react";
import type { FactorTemplate } from "../api/templates";
import { fetchTemplates } from "../api/templates";

const CATEGORIES = [
  { key: "", label: "全部", icon: Layers },
  { key: "momentum", label: "动量", icon: TrendingUp },
  { key: "value", label: "价值", icon: BarChart3 },
  { key: "volume", label: "量价", icon: Activity },
  { key: "volatility", label: "波动", icon: LineChart },
  { key: "technical", label: "技术", icon: Zap },
  { key: "composite", label: "复合", icon: Layers },
];

const DIFFICULTY_COLORS: Record<string, string> = {
  beginner: "bg-green-50 text-green-700",
  intermediate: "bg-amber-50 text-amber-700",
  advanced: "bg-purple-50 text-purple-700",
};

const DIFFICULTY_LABELS: Record<string, string> = {
  beginner: "入门",
  intermediate: "进阶",
  advanced: "高级",
};

interface Props {
  onUseTemplate: (expression: string, params?: { universe: string; holding_period: number; n_groups: number }) => void;
}

export default function TemplateGallery({ onUseTemplate }: Props) {
  const [templates, setTemplates] = useState<FactorTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState("");

  useEffect(() => {
    setLoading(true);
    fetchTemplates(activeCategory || undefined)
      .then(setTemplates)
      .catch(() => setTemplates([]))
      .finally(() => setLoading(false));
  }, [activeCategory]);

  return (
    <div className="space-y-4">
      {/* Category tabs */}
      <div className="flex flex-wrap gap-1.5">
        {CATEGORIES.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveCategory(key)}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeCategory === key
                ? "bg-blue-50 text-blue-700 ring-1 ring-blue-200"
                : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            <Icon className="h-3 w-3" />
            {label}
          </button>
        ))}
      </div>

      {/* Template cards */}
      {loading ? (
        <div className="text-center py-8 text-xs text-gray-400">加载模板中...</div>
      ) : templates.length === 0 ? (
        <div className="text-center py-8 text-xs text-gray-400">暂无模板</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {templates.map((t) => (
            <div
              key={t.id}
              className="group rounded-xl border border-gray-150 bg-white p-4 hover:shadow-md hover:border-blue-200 transition-all cursor-pointer"
              onClick={() => onUseTemplate(t.expression, t.suggested_params)}
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold text-gray-800">{t.name}</h3>
                <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${DIFFICULTY_COLORS[t.difficulty]}`}>
                  {DIFFICULTY_LABELS[t.difficulty]}
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-500 leading-relaxed">{t.description}</p>
              <code className="mt-2 block text-[11px] text-blue-600 font-mono truncate" title={t.expression}>
                {t.expression}
              </code>
              <div className="mt-2 flex items-center justify-between">
                <div className="flex gap-1">
                  {t.tags.map((tag) => (
                    <span key={tag} className="px-1.5 py-0.5 rounded bg-gray-50 text-[10px] text-gray-500">
                      {tag}
                    </span>
                  ))}
                </div>
                <span className="flex items-center gap-0.5 text-[10px] text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity">
                  一键回测 <ChevronRight className="h-3 w-3" />
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
