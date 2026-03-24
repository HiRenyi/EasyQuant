import { useState } from "react";
import { BarChart3, LogOut, X, UserCircle, Terminal, Copy, Check, ExternalLink, Sun, Moon } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useColorMode } from "../contexts/ColorModeContext";
import { useNavigate } from "react-router-dom";

export const APP_VERSION = "v2.3.0";

const CHANGELOG = [
  {
    version: "v2.3.0",
    date: "2026-03-24",
    items: [
      "新增深色/浅色主题切换按钮",
      "修复多因子组合回测中基本面因子（ROE/PE等）计算失败的问题",
      "修复因子对比页面基本面因子不可用的问题",
      "修复迭代优化报告持久化失败的问题",
      "前端架构优化，统一主题管理",
    ],
  },
  {
    version: "v2.2.0",
    date: "2026-03-24",
    items: [
      "新增暗色模式切换，支持深色/浅色主题",
      "支持涨跌颜色切换（红涨绿跌 / 绿涨红跌）",
      "前端架构优化，统一主题管理",
    ],
  },
  {
    version: "v2.1.0",
    date: "2026-03-23",
    items: [
      "因子中性化默认全部开启（行业+市值），无需手动勾选",
      "前端设置改为「取消中性化」操作，勾选即关闭",
      "MCP 工具（run_backtest/score_factor/run_anti_overfit/run_rolling_validation）新增 neutralize_industry/neutralize_cap 参数",
      "支持涨跌颜色切换（红涨绿跌 / 绿涨红跌）",
    ],
  },
  {
    version: "v2.0.0",
    date: "2026-03-23",
    items: [
      "新增技术指标支持：ema、sma、wma、rsi、macd、atr、boll_upper/lower/mid、obv",
      "修复因子对比页面 500 错误（NaN/Inf 导致 JSON 序列化失败）",
      "修复回测失败时错误信息显示为 [object Object] 的问题",
      "接入 rqdatac 作为主数据源，baostock 降级为 fallback",
      "新增全量数据预热脚本（2015-2025，全股票池）",
    ],
  },
  {
    version: "v1.9.0",
    date: "2026-03-23",
    items: [
      "新增模拟盘：回测结果一键上模拟盘，每日自动结算净值",
      "新增任务取消：回测运行中随时中止",
      "因子模板库新增「基本面」分类（PE/PB/ROE/ROA/PS/股息/现金流/营收增速）",
      "分享卡片改版：展示策略收益、超额收益等核心指标",
      "修复迭代优化对基本面因子（dupont_roe 等）验证失败的问题",
    ],
  },
  {
    version: "v1.8.0",
    date: "2026-03-22",
    items: [
      "新增 dividend_yield（股息率）变量，对接 baostock 分红数据 API",
      "股息率按 TTM（滚动12个月）累计分红 / 收盘价计算",
      "使用除权日做时点对齐，避免未来数据偏差",
      "基本面变量总数增至 27 个",
    ],
  },
  {
    version: "v1.7.1",
    date: "2026-03-22",
    items: [
      "新增 roa(总资产收益率)、bps(每股净资产)、nav(净资产) 3 个衍生变量",
      "表达式变量名支持大小写不敏感（ROE/roe/Roe 均可）",
      "LLM 常见错误变量名自动修正（pe_ratio→pe, eps→eps_ttm 等）",
      "不支持的变量给出清晰中文提示和替代建议",
    ],
  },
  {
    version: "v1.7.0",
    date: "2026-03-22",
    items: [
      "支持 23 个基本面财务变量（ROE/PE/PB/净利润率等）",
      "财务数据按报告发布日对齐，避免未来数据偏差",
      "进度条新增「获取财务数据」步骤",
      "预热沪深300/中证1000/中证2000 财务数据缓存",
    ],
  },
  {
    version: "v1.6.1",
    date: "2026-03-22",
    items: [
      "新增 MCP 集成指南：Header 一键查看 Claude Code / OpenClaw 配置教程",
      "支持 Claude Code 本地 stdio 和远程 HTTP 两种接入方式",
      "支持 OpenClaw Agent 通过 MCP 协议调用 8 个回测工具",
    ],
  },
  {
    version: "v1.6.0",
    date: "2026-03-22",
    items: [
      "新增游客模式：免登录即可体验回测（小样本股票池）",
      "新增精选因子墙：首页展示高分因子策略",
      "新增分享卡片：回测结果一键生成图片",
      "登录页重设计：展示产品核心功能",
      "SEO 优化：结构化数据、Open Graph 标签",
    ],
  },
  {
    version: "v1.5.1",
    date: "2026-03-21",
    items: [
      "多因子组合 / 因子对比页支持从因子库选择已收藏因子",
      "修复因子模板库为空的路径问题",
    ],
  },
  {
    version: "v1.5.0",
    date: "2026-03-21",
    items: [
      "新增因子模板库：经典因子模板一键回测",
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

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const { isDark } = useColorMode();
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className={`absolute top-2 right-2 p-1 rounded text-gray-400 ${isDark ? "hover:text-gray-300 hover:bg-gray-800" : "hover:text-gray-600 hover:bg-gray-100"} transition-colors`}
      title="复制"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

function McpGuideModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"claude" | "openclaw">("claude");
  const { isDark } = useColorMode();

  const mcpConfig = `{
  "mcpServers": {
    "quantgpt": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "quantgpt"],
      "env": {
        "PYTHONPATH": "/path/to/QuantGPT"
      }
    }
  }
}`;

  const openclawNativeCode = `from openclaw.tools.mcp import MCPClient

client = MCPClient(
    server_url="https://quantgpt.online/mcp"
)

agent = Agent(
    tools=client.get_tools()
)`;

  const openclawManualCode = `import requests

def backtest_tool(expression: str, **kwargs):
    return requests.post(
        "https://quantgpt.online/mcp",
        json={"expression": expression, **kwargs}
    ).json()

agent.register_tool(backtest_tool)`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className={`${isDark ? "bg-gray-900" : "bg-white"} rounded-2xl shadow-xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`flex items-center justify-between px-5 py-4 border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center">
              <Terminal className="h-4 w-4 text-white" />
            </div>
            <div>
              <h2 className={`text-base font-semibold ${isDark ? "text-gray-100" : "text-gray-900"}`}>MCP 集成指南</h2>
              <p className="text-xs text-gray-400">通过 MCP 协议接入 QuantGPT 回测能力</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className={`p-1.5 rounded-lg text-gray-400 ${isDark ? "hover:text-gray-300 hover:bg-gray-800" : "hover:text-gray-600 hover:bg-gray-100"} transition-colors`}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className={`px-5 pt-3 flex gap-1 border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
          <button
            onClick={() => setTab("claude")}
            className={`px-3 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              tab === "claude"
                ? isDark
                  ? "text-orange-400 border-b-2 border-orange-500 bg-orange-500/10"
                  : "text-orange-600 border-b-2 border-orange-500 bg-orange-50/50"
                : isDark
                  ? "text-gray-400 hover:text-gray-300 hover:bg-gray-800"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
            }`}
          >
            Claude Code
          </button>
          <button
            onClick={() => setTab("openclaw")}
            className={`px-3 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              tab === "openclaw"
                ? isDark
                  ? "text-amber-400 border-b-2 border-amber-500 bg-amber-500/10"
                  : "text-blue-600 border-b-2 border-blue-500 bg-blue-50/50"
                : isDark
                  ? "text-gray-400 hover:text-gray-300 hover:bg-gray-800"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
            }`}
          >
            OpenClaw / Agent
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-4 space-y-5">
          {tab === "claude" ? (
            <>
              {/* What is MCP */}
              <div className={`${isDark ? "bg-amber-500/10" : "bg-blue-50"} rounded-lg p-3.5`}>
                <p className={`text-sm ${isDark ? "text-amber-300" : "text-blue-800"}`}>
                  <span className="font-medium">什么是 MCP？</span>{" "}
                  MCP (Model Context Protocol) 让 Claude 直接调用 QuantGPT 的回测工具。
                  配置后，你可以在 Claude Code 终端中用自然语言执行因子回测。
                </p>
              </div>

              {/* Step 1: Clone */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`h-5 w-5 rounded-full ${isDark ? "bg-gray-100" : "bg-gray-900"} ${isDark ? "text-gray-900" : "text-white"} text-xs flex items-center justify-center font-medium`}>1</span>
                  <h3 className={`text-sm font-medium ${isDark ? "text-gray-100" : "text-gray-900"}`}>克隆项目并安装</h3>
                </div>
                <div className="relative bg-gray-900 rounded-lg p-3 font-mono text-xs text-gray-100 leading-relaxed">
                  <CopyButton text={"git clone https://github.com/Miasyster/QuantGPT.git\ncd QuantGPT\npip install -e ."} />
                  <pre className="whitespace-pre-wrap"><span className="text-green-400">$</span> git clone https://github.com/Miasyster/QuantGPT.git{"\n"}<span className="text-green-400">$</span> cd QuantGPT{"\n"}<span className="text-green-400">$</span> pip install -e .</pre>
                </div>
              </div>

              {/* Step 2: Configure */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`h-5 w-5 rounded-full ${isDark ? "bg-gray-100" : "bg-gray-900"} ${isDark ? "text-gray-900" : "text-white"} text-xs flex items-center justify-center font-medium`}>2</span>
                  <h3 className={`text-sm font-medium ${isDark ? "text-gray-100" : "text-gray-900"}`}>配置 MCP</h3>
                </div>
                <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"} mb-1.5 font-medium`}>在项目根目录创建 <code className={`${isDark ? "bg-gray-800" : "bg-gray-100"} px-1 rounded`}>.mcp.json</code>：</p>
                <div className="relative bg-gray-900 rounded-lg p-3 font-mono text-xs text-gray-100 leading-relaxed">
                  <CopyButton text={mcpConfig} />
                  <pre className="whitespace-pre-wrap">{mcpConfig}</pre>
                </div>
                <p className="text-xs text-gray-400 mt-1.5">
                  将 <code className={`${isDark ? "bg-gray-800 text-gray-300" : "bg-gray-100 text-gray-600"} px-1 rounded`}>PYTHONPATH</code> 替换为实际项目路径。需配置米筐数据源，详见项目 README。
                </p>
              </div>

              {/* Step 3 */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`h-5 w-5 rounded-full ${isDark ? "bg-gray-100" : "bg-gray-900"} ${isDark ? "text-gray-900" : "text-white"} text-xs flex items-center justify-center font-medium`}>3</span>
                  <h3 className={`text-sm font-medium ${isDark ? "text-gray-100" : "text-gray-900"}`}>开始使用</h3>
                </div>
                <div className="relative bg-gray-900 rounded-lg p-3 font-mono text-sm text-gray-100">
                  <CopyButton text="claude mcp list" />
                  <div>
                    <span className="text-green-400">$</span> claude mcp list<br/>
                    <span className="text-gray-400"># quantgpt: Connected</span>
                  </div>
                </div>
                <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"} mt-2`}>
                  验证连接后，直接用自然语言对话即可：「帮我测试一个低波动率因子，在沪深300上回测」
                </p>
              </div>
            </>
          ) : (
            <>
              {/* OpenClaw intro */}
              <div className={`${isDark ? "bg-amber-500/10" : "bg-blue-50"} rounded-lg p-3.5`}>
                <p className={`text-sm ${isDark ? "text-amber-300" : "text-blue-800"}`}>
                  <span className="font-medium">架构说明</span>{" "}
                  OpenClaw 是 Agent 调度框架，通过 MCP 协议动态调用 QuantGPT 的回测能力。
                  QuantGPT 作为 MCP Server 暴露标准化工具接口。
                </p>
              </div>

              {/* Architecture diagram */}
              <div className={`${isDark ? "bg-gray-800" : "bg-gray-50"} rounded-lg p-3`}>
                <pre className={`text-xs ${isDark ? "text-gray-400" : "text-gray-600"} leading-relaxed font-mono`}>{`[OpenClaw Agent]
      ↓
[MCP Client]
      ↓  Streamable HTTP
[QuantGPT MCP Server (quantgpt.online)]
      ↓
[回测 / 评分 / 诊断 / 验证]`}</pre>
              </div>

              {/* Step 1: Connect */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`h-5 w-5 rounded-full ${isDark ? "bg-gray-100" : "bg-gray-900"} ${isDark ? "text-gray-900" : "text-white"} text-xs flex items-center justify-center font-medium`}>1</span>
                  <h3 className={`text-sm font-medium ${isDark ? "text-gray-100" : "text-gray-900"}`}>在 Agent 中接入</h3>
                </div>
                <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"} mb-1.5`}>MCP 端点地址：<code className={`${isDark ? "bg-gray-800" : "bg-gray-100"} px-1 rounded`}>https://quantgpt.online/mcp</code></p>
                <div className="space-y-3">
                  <div>
                    <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"} mb-1.5 font-medium`}>方式 A：原生 MCP Client（推荐）</p>
                    <div className="relative bg-gray-900 rounded-lg p-3 font-mono text-xs text-gray-100 leading-relaxed">
                      <CopyButton text={openclawNativeCode} />
                      <pre className="whitespace-pre-wrap">{openclawNativeCode}</pre>
                    </div>
                  </div>
                  <div>
                    <p className={`text-xs ${isDark ? "text-gray-400" : "text-gray-500"} mb-1.5 font-medium`}>方式 B：手动封装（兼容旧版本）</p>
                    <div className="relative bg-gray-900 rounded-lg p-3 font-mono text-xs text-gray-100 leading-relaxed">
                      <CopyButton text={openclawManualCode} />
                      <pre className="whitespace-pre-wrap">{openclawManualCode}</pre>
                    </div>
                  </div>
                </div>
              </div>

              {/* Tips */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`h-5 w-5 rounded-full ${isDark ? "bg-gray-100" : "bg-gray-900"} ${isDark ? "text-gray-900" : "text-white"} text-xs flex items-center justify-center font-medium`}>2</span>
                  <h3 className={`text-sm font-medium ${isDark ? "text-gray-100" : "text-gray-900"}`}>注意事项</h3>
                </div>
                <div className="space-y-1.5">
                  {[
                    "Tool 描述必须清晰，LLM 依赖描述决定是否调用",
                    "输入参数要结构化（expression, start_date, end_date）",
                    "返回值保持精简，避免大 JSON",
                    "工具数量建议 ≤ 10 个，过多会导致调用混乱",
                  ].map((tip, i) => (
                    <div key={i} className={`flex items-start gap-2 text-xs ${isDark ? "text-gray-400" : "text-gray-600"}`}>
                      <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
                      {tip}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Available tools - shared */}
          <div>
            <h3 className={`text-sm font-medium ${isDark ? "text-gray-100" : "text-gray-900"} mb-2`}>可用工具（8 个）</h3>
            <div className="grid grid-cols-2 gap-1.5">
              {[
                { name: "list_operators", desc: "查看算子列表" },
                { name: "list_universes", desc: "查看股票池" },
                { name: "validate_expression", desc: "验证表达式" },
                { name: "run_backtest", desc: "执行回测" },
                { name: "score_factor", desc: "因子评分" },
                { name: "diagnose_factor", desc: "诊断因子" },
                { name: "run_anti_overfit", desc: "抗过拟合检测" },
                { name: "run_rolling_validation", desc: "滚动验证" },
              ].map((tool) => (
                <div key={tool.name} className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
                  <code className="text-xs text-orange-600 font-medium">{tool.name}</code>
                  <span className="text-xs text-gray-400">{tool.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className={`px-5 py-3 border-t ${isDark ? "border-gray-700" : "border-gray-100"} flex items-center justify-between`}>
          <a
            href="https://github.com/Miasyster/QuantGPT"
            target="_blank"
            rel="noopener noreferrer"
            className={`flex items-center gap-1.5 text-sm ${isDark ? "text-gray-400 hover:text-gray-300" : "text-gray-500 hover:text-gray-700"} transition-colors`}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            GitHub
          </a>
          <button
            onClick={onClose}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium ${isDark ? "text-gray-400 hover:bg-gray-800" : "text-gray-600 hover:bg-gray-100"} transition-colors`}
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}

function ColorModeToggle() {
  const { colorMode, toggleColorMode, isDark } = useColorMode();
  return (
    <button
      onClick={toggleColorMode}
      className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border ${isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-200 hover:bg-gray-50"} transition-colors`}
      title={colorMode === "cn" ? "当前：红涨绿跌（中国）" : "当前：绿涨红跌（西方）"}
    >
      <span className={colorMode === "cn" ? "text-red-500" : "text-emerald-500"}>涨</span>
      <span className="text-gray-300">/</span>
      <span className={colorMode === "cn" ? "text-emerald-500" : "text-red-500"}>跌</span>
    </button>
  );
}

function DarkModeToggle() {
  const { isDark, toggleDark } = useColorMode();
  return (
    <button
      onClick={toggleDark}
      className={`p-1.5 rounded-md border ${isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-200 hover:bg-gray-50"} transition-colors`}
      title={isDark ? "切换到浅色模式" : "切换到深色模式"}
    >
      {isDark ? <Sun className="h-3.5 w-3.5 text-amber-400" /> : <Moon className="h-3.5 w-3.5 text-gray-500" />}
    </button>
  );
}

export default function Header() {
  const { user, isGuest, logout } = useAuth();
  const { isDark } = useColorMode();
  const navigate = useNavigate();
  const [showChangelog, setShowChangelog] = useState(false);
  const [showMcpGuide, setShowMcpGuide] = useState(false);

  return (
    <>
      <header className={`border-b ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"}`}>
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className={`h-6 w-6 ${isDark ? "text-amber-400" : "text-blue-600"}`} />
            <div>
              <div className="flex items-center gap-2">
                <h1 className={`text-lg font-semibold ${isDark ? "text-gray-100" : "text-gray-900"}`}>QuantGPT</h1>
                <button
                  onClick={() => setShowChangelog(true)}
                  className={`text-xs px-1.5 py-0.5 rounded ${isDark ? "bg-amber-500/10 text-amber-400 hover:bg-amber-500/20" : "bg-blue-50 text-blue-600 hover:bg-blue-100"} transition-colors font-mono`}
                >
                  {APP_VERSION}
                </button>
              </div>
              <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>用自然语言描述你的因子策略，一键回测</p>
            </div>
          </div>
          {isGuest ? (
            <div className="flex items-center gap-3">
              <DarkModeToggle />
              <ColorModeToggle />
              <button
                onClick={() => setShowMcpGuide(true)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm text-orange-600 hover:bg-orange-50 transition-colors"
                title="MCP 集成指南"
              >
                <Terminal className="h-4 w-4" />
                <span className="hidden sm:inline">MCP</span>
              </button>
              <span className="flex items-center gap-1.5 text-sm text-amber-600">
                <UserCircle className="h-4 w-4" />
                游客模式
              </span>
              <button
                onClick={() => { logout(); navigate("/login"); }}
                className="px-3 py-1.5 rounded-lg text-sm font-medium text-blue-600 hover:bg-blue-50 transition-colors"
              >
                注册 / 登录
              </button>
            </div>
          ) : user ? (
            <div className="flex items-center gap-3">
              <DarkModeToggle />
              <ColorModeToggle />
              <button
                onClick={() => setShowMcpGuide(true)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm text-orange-600 hover:bg-orange-50 transition-colors"
                title="MCP 集成指南"
              >
                <Terminal className="h-4 w-4" />
                <span className="hidden sm:inline">MCP</span>
              </button>
              <span className={`text-sm ${isDark ? "text-gray-400" : "text-gray-600"}`}>{user.email}</span>
              <button
                onClick={logout}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm ${isDark ? "text-gray-400 hover:text-gray-300 hover:bg-gray-800" : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"} transition-colors`}
              >
                <LogOut className="h-4 w-4" />
                退出
              </button>
            </div>
          ) : null}
        </div>
      </header>

      {showChangelog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setShowChangelog(false)}
        >
          <div
            className={`${isDark ? "bg-gray-900" : "bg-white"} rounded-2xl shadow-xl w-full max-w-md mx-4 max-h-[80vh] flex flex-col`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={`flex items-center justify-between px-5 py-4 border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
              <div>
                <h2 className={`text-base font-semibold ${isDark ? "text-gray-100" : "text-gray-900"}`}>更新日志</h2>
                <p className="text-xs text-gray-400 mt-0.5">当前版本 {APP_VERSION}</p>
              </div>
              <button
                onClick={() => setShowChangelog(false)}
                className={`p-1.5 rounded-lg text-gray-400 ${isDark ? "hover:text-gray-300 hover:bg-gray-800" : "hover:text-gray-600 hover:bg-gray-100"} transition-colors`}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="overflow-y-auto px-5 py-4 space-y-5">
              {CHANGELOG.map((release) => (
                <div key={release.version}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-sm font-semibold ${isDark ? "text-gray-100" : "text-gray-900"} font-mono`}>{release.version}</span>
                    <span className="text-xs text-gray-400">{release.date}</span>
                    {release.version === APP_VERSION && (
                      <span className={`text-xs px-1.5 py-0.5 rounded ${isDark ? "bg-amber-500/10 text-amber-400" : "bg-blue-50 text-blue-600"}`}>当前</span>
                    )}
                  </div>
                  <ul className="space-y-1">
                    {release.items.map((item, i) => (
                      <li key={i} className={`flex items-start gap-2 text-sm ${isDark ? "text-gray-400" : "text-gray-600"}`}>
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

      {showMcpGuide && <McpGuideModal onClose={() => setShowMcpGuide(false)} />}
    </>
  );
}
