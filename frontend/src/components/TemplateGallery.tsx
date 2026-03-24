import { useState, useEffect } from "react";
import { Zap, TrendingUp, Activity, LineChart, Layers, ChevronRight, PieChart } from "lucide-react";
import { useColorMode } from "../contexts/ColorModeContext";
import type { FactorTemplate } from "../api/templates";
import { fetchTemplates } from "../api/templates";

const ALL_CATEGORIES = [
  { key: "", label: "全部", icon: Layers },
  { key: "trend", label: "趋势", icon: TrendingUp },
  { key: "volume", label: "量价", icon: Activity },
  { key: "volatility", label: "波动", icon: LineChart },
  { key: "technical", label: "技术", icon: Zap },
  { key: "valuation", label: "估值", icon: PieChart },
];

const getDifficultyColors = (isDark: boolean): Record<string, string> => ({
  beginner: isDark ? "bg-emerald-500/10 text-emerald-400" : "bg-green-50 text-green-700",
  intermediate: isDark ? "bg-amber-500/10 text-amber-400" : "bg-amber-50 text-amber-700",
  advanced: isDark ? "bg-purple-500/10 text-purple-400" : "bg-purple-50 text-purple-700",
});

const DIFFICULTY_LABELS: Record<string, string> = {
  beginner: "入门",
  intermediate: "进阶",
  advanced: "高级",
};

interface Props {
  onUseTemplate: (expression: string, params?: { universe: string; holding_period: number; n_groups: number }) => void;
}

export default function TemplateGallery({ onUseTemplate }: Props) {
  const { isDark } = useColorMode();
  const DIFFICULTY_COLORS = getDifficultyColors(isDark);
  const [templates, setTemplates] = useState<FactorTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState("");

  const CATEGORIES = ALL_CATEGORIES;

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
                ? isDark
                  ? "bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/30"
                  : "bg-blue-50 text-blue-700 ring-1 ring-blue-200"
                : isDark
                  ? "text-gray-400 hover:bg-gray-800"
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
              className={`group rounded-xl border ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-150 bg-white"} p-4 hover:shadow-md ${isDark ? "hover:border-amber-500/30" : "hover:border-blue-200"} transition-all cursor-pointer`}
              onClick={() => onUseTemplate(t.expression, t.suggested_params)}
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className={`text-sm font-semibold ${isDark ? "text-gray-200" : "text-gray-800"}`}>{t.name}</h3>
                <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${DIFFICULTY_COLORS[t.difficulty]}`}>
                  {DIFFICULTY_LABELS[t.difficulty]}
                </span>
              </div>
              <p className={`mt-1 text-xs ${isDark ? "text-gray-400" : "text-gray-500"} leading-relaxed`}>{t.description}</p>
              <code className={`mt-2 block text-[11px] ${isDark ? "text-amber-400" : "text-blue-600"} font-mono truncate`} title={t.expression}>
                {t.expression}
              </code>
              <div className="mt-2 flex items-center justify-between">
                <div className="flex gap-1">
                  {t.tags.map((tag) => (
                    <span key={tag} className={`px-1.5 py-0.5 rounded ${isDark ? "bg-gray-800" : "bg-gray-50"} text-[10px] ${isDark ? "text-gray-400" : "text-gray-500"}`}>
                      {tag}
                    </span>
                  ))}
                </div>
                <span className={`flex items-center gap-0.5 text-[10px] ${isDark ? "text-amber-500" : "text-blue-500"} opacity-0 group-hover:opacity-100 transition-opacity`}>
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
