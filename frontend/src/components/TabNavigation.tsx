import { FlaskConical, Layers, BarChart3, LineChart, Code, LayoutDashboard } from "lucide-react";

export type MainTab = "backtest" | "strategy" | "composite" | "comparison" | "paper" | "dashboard";

export const TABS: { id: MainTab; label: string; icon: typeof FlaskConical; color: string }[] = [
  { id: "dashboard", label: "研究总览", icon: LayoutDashboard, color: "amber" },
  { id: "backtest", label: "单因子回测", icon: FlaskConical, color: "blue" },
  { id: "strategy", label: "策略回测", icon: Code, color: "orange" },
  { id: "composite", label: "多因子组合", icon: Layers, color: "purple" },
  { id: "comparison", label: "因子对比", icon: BarChart3, color: "emerald" },
  { id: "paper", label: "模拟盘", icon: LineChart, color: "teal" },
];

interface Props {
  activeTab: MainTab;
  onTabChange: (tab: MainTab) => void;
  isDark: boolean;
}

export default function TabNavigation({ activeTab, onTabChange, isDark }: Props) {
  return (
    <div className={`border-b ${isDark ? "border-gray-800 bg-gray-900" : "border-gray-200 bg-white"}`}>
      <div className="mx-auto max-w-7xl px-6">
        <nav className="flex items-center gap-1 -mb-px">
          {/* Tab buttons */}
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  isActive
                    ? isDark
                      ? "border-blue-400 text-blue-400"
                      : `border-${tab.color}-600 text-${tab.color}-600`
                    : isDark
                      ? "border-transparent text-gray-500 hover:text-gray-300 hover:border-gray-700"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }`}
                style={isActive && !isDark ? {
                  borderBottomColor: tab.color === "blue" ? "#2563eb"
                    : tab.color === "rose" ? "#e11d48"
                    : tab.color === "indigo" ? "#4f46e5"
                    : tab.color === "amber" ? "#d97706"
                    : tab.color === "purple" ? "#9333ea"
                    : tab.color === "teal" ? "#0d9488"
                    : "#059669",
                  color: tab.color === "blue" ? "#2563eb"
                    : tab.color === "rose" ? "#e11d48"
                    : tab.color === "indigo" ? "#4f46e5"
                    : tab.color === "amber" ? "#d97706"
                    : tab.color === "purple" ? "#9333ea"
                    : tab.color === "teal" ? "#0d9488"
                    : "#059669",
                } : isActive && isDark ? {
                  borderBottomColor: "#60a5fa",
                  color: "#93bbfd",
                } : undefined}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
