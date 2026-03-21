import { useState } from "react";
import { BarChart3, LogOut, X } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

export const APP_VERSION = "v1.5.0";

const CHANGELOG = [
  {
    version: "v1.5.0",
    date: "2026-03-21",
    items: [
      "新增策略模板库：18个经典因子策略一键回测",
      "新增多因子组合回测 + 因子归因分析",
      "新增因子对比看板：并排比较多个因子表现",
      "新增方向引导迭代：指定 AI 迭代优化方向",
      "支持中证1000 / 全A市场股票池",
      "支持行业中性化 / 市值中性化",
      "AI 因子解读升级：新增评级、核心结论、改进建议",
      "页面重构：顶部 Tab 导航，功能区更清晰",
    ],
  },
  {
    version: "v1.4.0",
    date: "2026-03-21",
    items: [
      "新增「我的因子库」：收藏优质因子，跨会话保存",
      "侧边栏支持会话/因子库 Tab 切换",
      "回测结果页新增「收藏因子」按钮",
    ],
  },
  {
    version: "v1.3.0",
    date: "2026-03-21",
    items: [
      "修复历史会话迭代优化报错（Task not found）",
      "修复切换会话后迭代结果丢失",
      "迭代面板 Sharpe 指标与上方卡片保持一致",
    ],
  },
  {
    version: "v1.2.0",
    date: "2026-03-20",
    items: [
      "新增 AI 因子迭代优化功能",
      "新增管理后台用户增长趋势图",
      "支持直接输入因子表达式（跳过 LLM）",
      "新增日期特殊变量：day / weekday / month",
      "基准指标内联显示在总收益/年化卡片",
    ],
  },
  {
    version: "v1.1.0",
    date: "2026-03-15",
    items: [
      "新增反过拟合检测（4项测试）",
      "新增滚动验证（Walk-Forward）",
      "新增因子评分系统（0-100，A/B/C/D）",
      "优化中证500回测性能",
    ],
  },
  {
    version: "v1.0.0",
    date: "2026-03-01",
    items: [
      "上线自然语言因子回测",
      "支持沪深300 / 中证500 / 小样本股票池",
      "QuantStats HTML 报告生成",
      "MCP 工具集成",
    ],
  },
];

export default function Header() {
  const { user, logout } = useAuth();
  const [showChangelog, setShowChangelog] = useState(false);

  return (
    <>
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="h-6 w-6 text-blue-600" />
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold text-gray-900">QuantGPT</h1>
                <button
                  onClick={() => setShowChangelog(true)}
                  className="text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors font-mono"
                >
                  {APP_VERSION}
                </button>
              </div>
              <p className="text-sm text-gray-500">用自然语言描述你的因子策略，一键回测</p>
            </div>
          </div>
          {user && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600">{user.email}</span>
              <button
                onClick={logout}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
              >
                <LogOut className="h-4 w-4" />
                退出
              </button>
            </div>
          )}
        </div>
      </header>

      {showChangelog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setShowChangelog(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div>
                <h2 className="text-base font-semibold text-gray-900">更新日志</h2>
                <p className="text-xs text-gray-400 mt-0.5">当前版本 {APP_VERSION}</p>
              </div>
              <button
                onClick={() => setShowChangelog(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="overflow-y-auto px-5 py-4 space-y-5">
              {CHANGELOG.map((release) => (
                <div key={release.version}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-semibold text-gray-900 font-mono">{release.version}</span>
                    <span className="text-xs text-gray-400">{release.date}</span>
                    {release.version === APP_VERSION && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">当前</span>
                    )}
                  </div>
                  <ul className="space-y-1">
                    {release.items.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                        <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-gray-300 shrink-0" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
