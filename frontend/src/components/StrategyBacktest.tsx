import { useState, useEffect } from "react";
import { Send, Loader2, Check, Circle, ChevronDown, ChevronUp, TrendingUp, Activity, AlertTriangle, Wallet, RefreshCw, FileText } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { useStrategyBacktest } from "../hooks/useStrategyBacktest";
import { useColorMode } from "../contexts/ColorModeContext";
import type { StrategyTask, StrategyTaskStatus, StrategyBacktestResult, EquityCurvePoint } from "../types/strategy";

// ---- Props ----

interface StrategyBacktestProps {
  sessionId?: string | null;
  onComplete?: (task: StrategyTask) => void;
  restoredTask?: StrategyTask | null;
  onClearRestored?: () => void;
}

// ---- Visible Progress Steps (simplified, no internal details) ----

const VISIBLE_STEPS = [
  { key: "generating", label: "生成策略" },
  { key: "running", label: "运行回测" },
  { key: "scraping", label: "获取结果" },
  { key: "completed", label: "完成" },
] as const;

type VisibleStep = typeof VISIBLE_STEPS[number]["key"];

function getVisibleStep(status: StrategyTaskStatus): VisibleStep {
  switch (status) {
    case "pending":
    case "generating_code":
    case "validating_code":
      return "generating";
    case "logging_in":
    case "launching_browser":
    case "setting_code":
    case "configuring_backtest":
    case "running_backtest":
    case "waiting_completion":
      return "running";
    case "scraping_results":
      return "scraping";
    case "completed":
      return "completed";
    default:
      return "generating";
  }
}

const VISIBLE_STEP_ORDER: VisibleStep[] = ["generating", "running", "scraping", "completed"];

// ---- Example prompts ----

const EXAMPLE_PROMPTS = [
  "帮我写一个双均线策略，5日上穿20日买入，下穿卖出",
  "写一个 MACD 趋势跟踪策略",
  "帮我构建一个布林带均值回归策略",
  "写一个基于 RSI 指标的超买超卖策略",
  "做一个沪深300成分股的动量策略",
  "帮我写一个海龟交易法则策略",
];

const INITIAL_CAPITAL = 1_000_000;

// ---- Main Component ----

export default function StrategyBacktest({
  sessionId,
  onComplete,
  restoredTask,
  onClearRestored,
}: StrategyBacktestProps) {
  const { isDark } = useColorMode();
  const { activeTask, setActiveTask, isLoading, submit, cancel } = useStrategyBacktest(onComplete, sessionId);

  const [prompt, setPrompt] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [settings, setSettings] = useState({
    start_date: "2023-01-01",
    end_date: "2025-12-31",
    benchmark: "000300.XSHG",
  });

  // Determine which task to display: active (in-flight) takes priority, then restored (history)
  const displayTask = activeTask ?? restoredTask ?? null;

  // When user clicks a history item, clear any active task
  useEffect(() => {
    if (restoredTask && !isLoading) {
      setActiveTask(null);
    }
  }, [restoredTask, isLoading, setActiveTask]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isLoading) return;
    onClearRestored?.();
    submit({ prompt: prompt.trim(), ...settings, initial_capital: INITIAL_CAPITAL });
  };

  const handleRerun = (task: StrategyTask) => {
    const p = task.result?.params ?? task.params;
    if (!p?.prompt) return;
    onClearRestored?.();
    setPrompt(p.prompt);
    submit({
      prompt: p.prompt,
      start_date: p.start_date ?? settings.start_date,
      end_date: p.end_date ?? settings.end_date,
      initial_capital: INITIAL_CAPITAL,
      benchmark: p.benchmark ?? settings.benchmark,
    });
  };

  const bg = isDark ? "bg-gray-900" : "bg-white";
  const border = isDark ? "border-gray-700" : "border-gray-200";
  const muted = isDark ? "text-gray-400" : "text-gray-500";

  return (
    <div className="space-y-4">
      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className={`rounded-xl border overflow-hidden transition-shadow ${border} ${bg} focus-within:ring-2 focus-within:ring-orange-500/20 focus-within:border-orange-500`}>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(e); } }}
            placeholder="描述你的交易策略..."
            rows={3}
            disabled={isLoading}
            className={`w-full px-4 py-3 resize-none focus:outline-none text-sm ${isDark ? "bg-gray-900 text-gray-100 placeholder-gray-500" : "bg-white text-gray-900 placeholder-gray-400"}`}
          />
          <div className={`flex items-center justify-between px-3 py-2 border-t ${isDark ? "border-gray-800" : "border-gray-100"}`}>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className={`flex items-center gap-1 text-xs ${muted} hover:${isDark ? "text-gray-300" : "text-gray-700"} transition-colors`}
            >
              {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              回测参数
            </button>
            <button
              type="submit"
              disabled={!prompt.trim() || isLoading}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-orange-600 text-white text-sm font-medium hover:bg-orange-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              {isLoading ? "运行中..." : "开始回测"}
            </button>
          </div>
        </div>

        {/* Advanced settings */}
        {showAdvanced && (
          <div className={`rounded-xl border ${border} ${bg} p-4 grid grid-cols-2 md:grid-cols-3 gap-3`}>
            <label className="space-y-1">
              <span className={`text-xs ${muted}`}>开始日期</span>
              <input type="date" value={settings.start_date} onChange={(e) => setSettings(s => ({ ...s, start_date: e.target.value }))}
                className={`w-full px-2 py-1.5 text-xs rounded-lg border ${border} ${bg} focus:outline-none focus:ring-1 focus:ring-orange-500`} />
            </label>
            <label className="space-y-1">
              <span className={`text-xs ${muted}`}>结束日期</span>
              <input type="date" value={settings.end_date} onChange={(e) => setSettings(s => ({ ...s, end_date: e.target.value }))}
                className={`w-full px-2 py-1.5 text-xs rounded-lg border ${border} ${bg} focus:outline-none focus:ring-1 focus:ring-orange-500`} />
            </label>
            <label className="space-y-1">
              <span className={`text-xs ${muted}`}>基准</span>
              <select value={settings.benchmark} onChange={(e) => setSettings(s => ({ ...s, benchmark: e.target.value }))}
                className={`w-full px-2 py-1.5 text-xs rounded-lg border ${border} ${bg} focus:outline-none focus:ring-1 focus:ring-orange-500`}>
                <option value="000300.XSHG">沪深300</option>
                <option value="000905.XSHG">中证500</option>
                <option value="000016.XSHG">上证50</option>
                <option value="399006.XSHE">创业板指</option>
              </select>
            </label>
          </div>
        )}
      </form>

      {/* Example prompts (when no task) */}
      {!displayTask && !isLoading && (
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_PROMPTS.map((p) => (
            <button
              key={p}
              onClick={() => setPrompt(p)}
              className={`text-xs px-3 py-1.5 rounded-lg border ${border} ${isDark ? "hover:bg-gray-800" : "hover:bg-gray-50"} ${muted} transition-colors`}
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Progress */}
      {displayTask && displayTask.status !== "completed" && displayTask.status !== "failed" && (
        <StrategyProgress status={displayTask.status} onCancel={cancel} isDark={isDark} />
      )}

      {/* Error */}
      {displayTask?.status === "failed" && (
        <div className={`rounded-xl border ${isDark ? "border-red-800 bg-red-900/20" : "border-red-200 bg-red-50"} p-4`}>
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className={`h-4 w-4 ${isDark ? "text-red-400" : "text-red-600"}`} />
            <span className={`text-sm font-medium ${isDark ? "text-red-400" : "text-red-600"}`}>回测失败</span>
          </div>
          <p className={`text-sm ${isDark ? "text-red-300" : "text-red-700"}`}>{displayTask.error || "未知错误"}</p>
        </div>
      )}

      {/* Results */}
      {displayTask?.status === "completed" && displayTask.result && (
        <StrategyResults result={displayTask.result} isDark={isDark} onRerun={() => handleRerun(displayTask)} />
      )}
    </div>
  );
}

// ---- Progress Component ----

function StrategyProgress({ status, onCancel, isDark }: {
  status: StrategyTaskStatus;
  onCancel?: () => void;
  isDark: boolean;
}) {
  const visibleStep = getVisibleStep(status);
  const currentIdx = VISIBLE_STEP_ORDER.indexOf(visibleStep);
  const border = isDark ? "border-gray-700" : "border-gray-200";

  return (
    <div className={`rounded-xl border ${border} ${isDark ? "bg-gray-900" : "bg-white"} p-5`}>
      <div className="flex items-center gap-1">
        {VISIBLE_STEPS.map((step, i) => {
          const stepIdx = VISIBLE_STEP_ORDER.indexOf(step.key);
          const isDone = currentIdx > stepIdx;
          const isActive = currentIdx === stepIdx;

          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1.5">
                <div className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                  isDone
                    ? isDark ? "bg-emerald-500/10 text-emerald-400" : "bg-emerald-100 text-emerald-600"
                    : isActive
                      ? isDark ? "bg-orange-500/10 text-orange-400" : "bg-orange-100 text-orange-600"
                      : isDark ? "bg-gray-800 text-gray-600" : "bg-gray-100 text-gray-400"
                }`}>
                  {isDone ? <Check className="h-3.5 w-3.5" /> : isActive ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Circle className="h-2.5 w-2.5" />}
                </div>
                <span className={`text-[10px] whitespace-nowrap ${isDone ? (isDark ? "text-emerald-400" : "text-emerald-600") : isActive ? (isDark ? "text-orange-400" : "text-orange-600") : (isDark ? "text-gray-600" : "text-gray-400")}`}>
                  {step.label}
                </span>
              </div>
              {i < VISIBLE_STEPS.length - 1 && (
                <div className={`h-px flex-1 mx-1 ${isDone ? (isDark ? "bg-emerald-500/30" : "bg-emerald-200") : (isDark ? "bg-gray-800" : "bg-gray-200")}`} />
              )}
            </div>
          );
        })}
      </div>

      {onCancel && (
        <div className="mt-3 text-center">
          <button onClick={onCancel} className={`text-xs ${isDark ? "text-gray-500 hover:text-gray-300" : "text-gray-400 hover:text-gray-600"} transition-colors`}>
            取消
          </button>
        </div>
      )}
    </div>
  );
}

// ---- Results Component ----

function StrategyResults({ result, isDark, onRerun }: {
  result: StrategyBacktestResult;
  isDark: boolean;
  onRerun: () => void;
}) {
  const [activeTab, setActiveTab] = useState<"chart" | "trades" | "positions">("chart");
  const [showDetails, setShowDetails] = useState(false);
  const border = isDark ? "border-gray-700" : "border-gray-200";
  const bg = isDark ? "bg-gray-900" : "bg-white";
  const muted = isDark ? "text-gray-400" : "text-gray-500";

  const metrics = result.metrics;
  const params = result.params;

  return (
    <div className="space-y-4">
      {/* Action bar: rerun + details toggle */}
      <div className="flex items-center gap-2">
        <button
          onClick={onRerun}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border ${border} ${isDark ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-50 text-gray-600"} transition-colors`}
        >
          <RefreshCw className="h-3 w-3" />
          重新运行
        </button>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border ${border} ${isDark ? "hover:bg-gray-800 text-gray-300" : "hover:bg-gray-50 text-gray-600"} transition-colors`}
        >
          <FileText className="h-3 w-3" />
          回测详情
          {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
      </div>

      {/* Backtest details (collapsible) — full traceability chain */}
      {showDetails && (
        <div className={`rounded-xl border ${border} ${bg} p-4 space-y-3`}>
          {/* Prompt */}
          {params?.prompt && (
            <div>
              <p className={`text-xs font-medium ${muted} mb-1`}>策略描述</p>
              <p className={`text-sm ${isDark ? "text-gray-200" : "text-gray-800"}`}>{params.prompt}</p>
            </div>
          )}
          {/* Params */}
          <div>
            <p className={`text-xs font-medium ${muted} mb-1`}>回测参数</p>
            <div className="flex flex-wrap gap-3 text-xs">
              {params?.start_date && <span>{params.start_date} ~ {params.end_date}</span>}
              {params?.benchmark && <span>基准: {params.benchmark}</span>}
              <span>初始资金: ¥{(params?.initial_capital ?? INITIAL_CAPITAL).toLocaleString()}</span>
            </div>
          </div>
        </div>
      )}

      {/* Metric Cards */}
      <MetricCards metrics={metrics} isDark={isDark} border={border} bg={bg} muted={muted} />

      {/* Equity Curve Chart */}
      {result.equity_curve.length > 0 && (
        <div className={`rounded-xl border ${border} ${bg} p-4`}>
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="h-4 w-4 text-orange-500" />
            <span className="text-sm font-medium">净值曲线</span>
            <span className={`text-xs ${muted}`}>
              ({result.equity_curve[0].date} ~ {result.equity_curve[result.equity_curve.length - 1].date})
            </span>
          </div>
          <EquityCurveChart data={result.equity_curve} isDark={isDark} />
        </div>
      )}

      {/* Tabs: Trades / Positions */}
      {(result.trades.length > 0 || result.daily_positions.length > 0) && (
        <div className={`rounded-xl border ${border} ${bg} overflow-hidden`}>
          <div className={`flex border-b ${border}`}>
            {result.trades.length > 0 && (
              <button
                onClick={() => setActiveTab("trades")}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium transition-colors ${
                  activeTab === "trades"
                    ? isDark ? "text-orange-400 border-b-2 border-orange-400" : "text-orange-600 border-b-2 border-orange-600"
                    : muted
                }`}
              >
                <Activity className="h-3.5 w-3.5" />
                交易详情 ({result.trades.length})
              </button>
            )}
            {result.daily_positions.length > 0 && (
              <button
                onClick={() => setActiveTab("positions")}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium transition-colors ${
                  activeTab === "positions"
                    ? isDark ? "text-orange-400 border-b-2 border-orange-400" : "text-orange-600 border-b-2 border-orange-600"
                    : muted
                }`}
              >
                <Wallet className="h-3.5 w-3.5" />
                每日持仓 ({result.daily_positions.length})
              </button>
            )}
          </div>

          {activeTab === "trades" && result.trades.length > 0 && (
            <DataTable data={result.trades} isDark={isDark} border={border} muted={muted} maxRows={100} />
          )}

          {activeTab === "positions" && result.daily_positions.length > 0 && (
            <DataTable data={result.daily_positions} isDark={isDark} border={border} muted={muted} maxRows={100} />
          )}
        </div>
      )}
    </div>
  );
}

// ---- Metric Cards ----

function MetricCards({ metrics, isDark, border, bg, muted }: {
  metrics: StrategyBacktestResult["metrics"];
  isDark: boolean;
  border: string;
  bg: string;
  muted: string;
}) {
  const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;
  const fmtNum = (v: number) => v.toFixed(3);

  type ColorResult = "green" | "red" | "neutral";
  const cards: { label: string; value?: number; fmt: (v: number) => string; colorFn: (v: number) => ColorResult }[] = [
    { label: "策略收益", value: metrics.total_return, fmt: fmtPct, colorFn: (v: number): ColorResult => v >= 0 ? "green" : "red" },
    { label: "年化收益", value: metrics.annual_return, fmt: fmtPct, colorFn: (v: number): ColorResult => v >= 0 ? "green" : "red" },
    { label: "基准收益", value: metrics.benchmark_return, fmt: fmtPct, colorFn: (v: number): ColorResult => v >= 0 ? "green" : "red" },
    { label: "超额收益", value: metrics.excess_return, fmt: fmtPct, colorFn: (v: number): ColorResult => v >= 0 ? "green" : "red" },
    { label: "夏普比率", value: metrics.sharpe_ratio, fmt: fmtNum, colorFn: (v: number): ColorResult => v >= 1 ? "green" : v >= 0 ? "neutral" : "red" },
    { label: "索提诺比率", value: metrics.sortino_ratio, fmt: fmtNum, colorFn: (v: number): ColorResult => v >= 1 ? "green" : v >= 0 ? "neutral" : "red" },
    { label: "最大回撤", value: metrics.max_drawdown, fmt: fmtPct, colorFn: (): ColorResult => "red" },
    { label: "波动率", value: metrics.volatility, fmt: fmtPct, colorFn: (): ColorResult => "neutral" },
    { label: "Alpha", value: metrics.alpha, fmt: fmtNum, colorFn: (v: number): ColorResult => v >= 0 ? "green" : "red" },
    { label: "Beta", value: metrics.beta, fmt: fmtNum, colorFn: (): ColorResult => "neutral" },
    { label: "信息比率", value: metrics.information_ratio, fmt: fmtNum, colorFn: (v: number): ColorResult => v >= 0 ? "green" : "red" },
    { label: "胜率", value: metrics.win_rate, fmt: fmtPct, colorFn: (v: number): ColorResult => v >= 0.5 ? "green" : "red" },
  ].filter(c => c.value !== undefined && c.value !== null);

  if (cards.length === 0) return null;

  const colorMap = {
    green: isDark ? "text-emerald-400" : "text-emerald-600",
    red: isDark ? "text-red-400" : "text-red-600",
    neutral: isDark ? "text-gray-300" : "text-gray-700",
  };

  return (
    <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {cards.map((card) => (
        <div key={card.label} className={`rounded-xl border ${border} ${bg} p-3 text-center`}>
          <p className={`text-xs ${muted} mb-1`}>{card.label}</p>
          <p className={`text-lg font-bold ${colorMap[card.colorFn(card.value!)]}`}>
            {card.fmt(card.value!)}
          </p>
        </div>
      ))}
    </div>
  );
}

// ---- Equity Curve Chart (starting from 1,000,000) ----

function EquityCurveChart({ data, isDark }: {
  data: EquityCurvePoint[];
  isDark: boolean;
}) {
  const chartData = data.map((d) => ({
    date: d.date,
    strategy: Math.round((1 + d.strategy_return) * INITIAL_CAPITAL),
    benchmark: Math.round((1 + d.benchmark_return) * INITIAL_CAPITAL),
  }));

  const sampled = chartData.length > 500
    ? chartData.filter((_, i) => i % Math.ceil(chartData.length / 500) === 0 || i === chartData.length - 1)
    : chartData;

  const gridColor = isDark ? "#374151" : "#e5e7eb";
  const textColor = isDark ? "#9ca3af" : "#6b7280";

  const fmtValue = (v: number) => `${(v / 10000).toFixed(1)}万`;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={sampled} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: textColor }}
          tickFormatter={(v) => v.substring(5)}
          interval="preserveStartEnd"
          minTickGap={60}
        />
        <YAxis
          tick={{ fontSize: 10, fill: textColor }}
          tickFormatter={fmtValue}
          domain={["auto", "auto"]}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: isDark ? "#1f2937" : "#ffffff",
            border: `1px solid ${isDark ? "#374151" : "#e5e7eb"}`,
            borderRadius: "8px",
            fontSize: "12px",
            color: isDark ? "#e5e7eb" : "#111827",
          }}
          formatter={(value, name) => [
            `¥${Number(value).toLocaleString()}`,
            name === "strategy" ? "策略净值" : "基准净值",
          ]}
          labelFormatter={(label) => `日期: ${label}`}
        />
        <Legend
          formatter={(value) => value === "strategy" ? "策略" : "基准"}
          wrapperStyle={{ fontSize: "12px", color: textColor }}
        />
        <Line
          type="monotone"
          dataKey="strategy"
          stroke="#f97316"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
        <Line
          type="monotone"
          dataKey="benchmark"
          stroke={isDark ? "#6b7280" : "#9ca3af"}
          strokeWidth={1.5}
          dot={false}
          strokeDasharray="4 4"
          activeDot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ---- Generic Data Table ----

function DataTable({ data, isDark, border, muted, maxRows }: {
  data: Record<string, unknown>[];
  isDark: boolean;
  border: string;
  muted: string;
  maxRows: number;
}) {
  if (data.length === 0) return null;

  const headers = Object.keys(data[0]);
  const displayed = data.slice(0, maxRows);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className={isDark ? "bg-gray-800" : "bg-gray-50"}>
            {headers.map((h) => (
              <th key={h} className="text-left px-3 py-2 font-medium whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayed.map((row, i) => (
            <tr key={i} className={`border-t ${border} ${isDark ? "hover:bg-gray-800/50" : "hover:bg-gray-50"}`}>
              {headers.map((h) => {
                const val = String(row[h] ?? "");
                const isBuy = val === "买入" || val.toLowerCase().includes("buy");
                const isSell = val === "卖出" || val.toLowerCase().includes("sell");
                const cellColor = isBuy
                  ? isDark ? "text-emerald-400" : "text-emerald-600"
                  : isSell
                    ? isDark ? "text-red-400" : "text-red-600"
                    : "";
                return (
                  <td key={h} className={`px-3 py-1.5 whitespace-nowrap ${cellColor}`}>{val}</td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > maxRows && (
        <div className={`text-center py-2 text-xs ${muted}`}>显示前 {maxRows} 条，共 {data.length} 条</div>
      )}
    </div>
  );
}
