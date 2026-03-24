import { useState, useEffect, useCallback, useRef } from "react";
import {
  Calendar, TrendingUp, TrendingDown, Minus, Loader2,
  ArrowUp, ArrowDown, ArrowRight, Zap, Activity, Share2, Download, X, Check,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useColorMode } from "../contexts/ColorModeContext";

// ─── Types ───────────────────────────────────────────────────────

interface FactorSignalData {
  factor_id: string;
  factor_name: string;
  category: string;
  signal_description?: string;
  direction: string;
  dispersion: string;
  today_mean?: number;
  yesterday_mean?: number;
  top_stocks: [string, number][];
  bottom_stocks: [string, number][];
  percentile_20d?: number;
  zscore_20d?: number;
  signal_strength?: number;
}

interface SummaryMetrics {
  hs300_change?: number;
  sz50_change?: number;
  zz500_change?: number;
  csi1000_change?: number;
  factor_signals?: FactorSignalData[];
  factor_count?: number;
  regime?: string;
  style?: string;
  risk_level?: string;
  dominant_category?: string;
  headline?: string;
  [key: string]: unknown;
}

interface SummaryItem {
  id: string;
  date: string;
  title: string;
  metrics: SummaryMetrics | null;
  created_at: string | null;
}

interface SummaryDetail {
  id: string;
  date: string;
  title: string;
  content: string;
  metrics: SummaryMetrics | null;
}

// ─── Constants ───────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  trend: "趋势",
  volume: "量价",
  volatility: "波动",
  technical: "技术",
  valuation: "估值",
};

const CATEGORY_ORDER = ["trend", "volume", "volatility", "technical", "valuation"];

// ─── Index Cards ─────────────────────────────────────────────────

function IndexCard({ label, change, isDark }: { label: string; change: number; isDark: boolean }) {
  const { positiveClass, negativeClass } = useColorMode();
  const isUp = change > 0;
  const isFlat = change === 0;
  const Icon = isUp ? TrendingUp : isFlat ? Minus : TrendingDown;
  const colorClass = isUp ? positiveClass : isFlat ? "text-gray-500" : negativeClass;

  return (
    <div className={`rounded-lg border px-4 py-3 ${
      isDark ? "border-gray-700 bg-gray-800" : "border-gray-200 bg-white"
    }`}>
      <p className={`text-xs mb-1 ${isDark ? "text-gray-400" : "text-gray-500"}`}>{label}</p>
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${colorClass}`} />
        <span className={`text-lg font-bold ${colorClass}`}>
          {isUp ? "+" : ""}{change.toFixed(2)}%
        </span>
      </div>
    </div>
  );
}

// ─── Layer 1: Market State Card ──────────────────────────────────

const REGIME_CONFIG: Record<string, { icon: typeof Zap; color: string; bgLight: string; bgDark: string }> = {
  "趋势市": { icon: TrendingUp, color: "text-blue-600", bgLight: "bg-blue-50", bgDark: "bg-blue-500/10" },
  "震荡市": { icon: Activity, color: "text-amber-600", bgLight: "bg-amber-50", bgDark: "bg-amber-500/10" },
  "高波动": { icon: Zap, color: "text-red-600", bgLight: "bg-red-50", bgDark: "bg-red-500/10" },
};

const RISK_CONFIG: Record<string, { label: string; dotClass: string; textClass: string }> = {
  "低": { label: "低风险", dotClass: "bg-emerald-500", textClass: "text-emerald-600" },
  "中": { label: "中风险", dotClass: "bg-amber-500", textClass: "text-amber-600" },
  "高": { label: "高风险", dotClass: "bg-red-500", textClass: "text-red-600" },
};

function MarketStateCard({ metrics, isDark }: { metrics: SummaryMetrics; isDark: boolean }) {
  const { regime, style, risk_level, dominant_category, headline } = metrics;
  if (!regime) return null;

  const regimeCfg = REGIME_CONFIG[regime] ?? REGIME_CONFIG["震荡市"];
  const riskCfg = RISK_CONFIG[risk_level ?? "低"] ?? RISK_CONFIG["低"];
  const RegimeIcon = regimeCfg.icon;

  return (
    <div className={`rounded-xl border p-4 ${
      isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"
    }`}>
      <div className="grid grid-cols-4 gap-3 mb-3">
        <div className={`rounded-lg px-3 py-2.5 ${isDark ? regimeCfg.bgDark : regimeCfg.bgLight}`}>
          <p className={`text-[10px] mb-0.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>市场状态</p>
          <div className="flex items-center gap-1.5">
            <RegimeIcon className={`h-4 w-4 ${isDark ? "text-gray-200" : regimeCfg.color}`} />
            <span className={`text-sm font-bold ${isDark ? "text-gray-100" : regimeCfg.color}`}>{regime}</span>
          </div>
        </div>
        <div className={`rounded-lg px-3 py-2.5 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
          <p className={`text-[10px] mb-0.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>风格</p>
          <span className={`text-sm font-semibold ${isDark ? "text-gray-200" : "text-gray-800"}`}>
            {style ?? "-"}
          </span>
        </div>
        <div className={`rounded-lg px-3 py-2.5 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
          <p className={`text-[10px] mb-0.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>风险等级</p>
          <div className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${riskCfg.dotClass}`} />
            <span className={`text-sm font-semibold ${isDark ? "text-gray-200" : riskCfg.textClass}`}>
              {riskCfg.label}
            </span>
          </div>
        </div>
        <div className={`rounded-lg px-3 py-2.5 ${isDark ? "bg-gray-800" : "bg-gray-50"}`}>
          <p className={`text-[10px] mb-0.5 ${isDark ? "text-gray-400" : "text-gray-500"}`}>主导因子</p>
          <span className={`text-sm font-semibold ${isDark ? "text-gray-200" : "text-gray-800"}`}>
            {CATEGORY_LABELS[dominant_category ?? ""] ?? dominant_category ?? "-"}
          </span>
        </div>
      </div>
      {headline && (
        <div className={`rounded-lg px-3 py-2 ${
          isDark ? "bg-gray-800/60 border border-gray-700" : "bg-gray-50 border border-gray-100"
        }`}>
          <p className={`text-sm font-medium ${isDark ? "text-gray-200" : "text-gray-700"}`}>
            {headline}
          </p>
        </div>
      )}
    </div>
  );
}

// ─── Layer 2: Factor Signal Cards (card grid) ────────────────────

function FactorSignalCard({ signal, isDark }: { signal: FactorSignalData; isDark: boolean }) {
  const { positiveClass, negativeClass, colorMode } = useColorMode();
  const isUp = signal.direction === "转强";
  const isDown = signal.direction === "转弱";
  const Icon = isUp ? ArrowUp : isDown ? ArrowDown : ArrowRight;
  const dirColor = isUp ? positiveClass : isDown ? negativeClass : (isDark ? "text-gray-400" : "text-gray-500");

  const isCnMode = colorMode === "cn";
  const positiveBorder = isCnMode ? "border-l-red-500" : "border-l-emerald-500";
  const negativeBorder = isCnMode ? "border-l-emerald-500" : "border-l-red-500";
  const positiveBg = isCnMode
    ? (isDark ? "bg-red-500/5" : "bg-red-50/60")
    : (isDark ? "bg-emerald-500/5" : "bg-emerald-50/60");
  const negativeBg = isCnMode
    ? (isDark ? "bg-emerald-500/5" : "bg-emerald-50/60")
    : (isDark ? "bg-red-500/5" : "bg-red-50/60");

  const borderAccent = isUp
    ? positiveBorder
    : isDown
      ? negativeBorder
      : isDark ? "border-l-gray-600" : "border-l-gray-300";

  const bgTint = isUp
    ? positiveBg
    : isDown
      ? negativeBg
      : isDark ? "bg-gray-800/50" : "bg-gray-50/60";

  const dispBg = signal.dispersion === "高分化"
    ? isDark ? "bg-amber-500/10 text-amber-400" : "bg-amber-50 text-amber-700"
    : signal.dispersion === "低分化"
      ? isDark ? "bg-blue-500/10 text-blue-400" : "bg-blue-50 text-blue-600"
      : isDark ? "bg-gray-700 text-gray-400" : "bg-gray-100 text-gray-500";

  // Percentile bar (if available)
  const hasPct = signal.percentile_20d != null;
  const pct = signal.percentile_20d ?? 50;
  const pctHigh = pct >= 80;
  const pctLow = pct <= 20;
  const pctBarColor = pctHigh ? "bg-amber-500" : pctLow ? "bg-blue-500" : isDark ? "bg-gray-500" : "bg-gray-400";

  return (
    <div className={`rounded-lg border-l-[3px] border ${borderAccent} ${
      isDark ? "border-gray-700" : "border-gray-150"
    } ${bgTint} px-3 py-2.5 transition-shadow hover:shadow-sm`}>
      {/* Row 1: name + direction badge */}
      <div className="flex items-center justify-between gap-2">
        <span className={`text-sm font-semibold ${isDark ? "text-gray-100" : "text-gray-800"}`}>
          {signal.factor_name}
        </span>
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${dirColor}`}>
          <Icon className="h-3.5 w-3.5" />
          {signal.direction}
        </span>
      </div>
      {/* Row 2: signal description */}
      {signal.signal_description && (
        <p className={`mt-1 text-[11px] leading-relaxed ${isDark ? "text-gray-400" : "text-gray-500"}`}>
          {signal.signal_description}
        </p>
      )}
      {/* Row 3: percentile bar + z-score + dispersion */}
      <div className="mt-1.5 flex items-center gap-2 flex-wrap">
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${dispBg}`}>
          {signal.dispersion}
        </span>
        {hasPct && (
          <div className="flex items-center gap-1 min-w-[70px]">
            <div className={`h-1 rounded-full flex-1 ${isDark ? "bg-gray-700" : "bg-gray-200"}`}>
              <div
                className={`h-1 rounded-full ${pctBarColor}`}
                style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
              />
            </div>
            <span className={`text-[10px] tabular-nums ${
              pctHigh || pctLow
                ? isDark ? "text-amber-400 font-medium" : "text-amber-700 font-medium"
                : isDark ? "text-gray-500" : "text-gray-400"
            }`}>
              P{pct.toFixed(0)}
            </span>
          </div>
        )}
        {signal.zscore_20d != null && (
          <span className={`text-[10px] tabular-nums ${
            Math.abs(signal.zscore_20d) >= 1.5
              ? isDark ? "text-amber-400 font-medium" : "text-amber-700 font-medium"
              : isDark ? "text-gray-500" : "text-gray-400"
          }`}>
            z={signal.zscore_20d > 0 ? "+" : ""}{signal.zscore_20d.toFixed(1)}
          </span>
        )}
      </div>
    </div>
  );
}

function FactorSignalPanel({ signals, isDark }: { signals: FactorSignalData[]; isDark: boolean }) {
  if (!signals || signals.length === 0) return null;

  const { positiveClass, negativeClass } = useColorMode();

  const upCount = signals.filter((s) => s.direction === "转强").length;
  const downCount = signals.filter((s) => s.direction === "转弱").length;
  const flatCount = signals.filter((s) => s.direction === "持平").length;

  return (
    <div className={`rounded-xl border p-4 ${
      isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"
    }`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className={`text-sm font-semibold ${isDark ? "text-gray-200" : "text-gray-700"}`}>
          因子信号
        </h3>
        <div className="flex items-center gap-3 text-xs">
          {upCount > 0 && (
            <span className={`flex items-center gap-1 font-medium ${positiveClass}`}>
              <ArrowUp className="h-3 w-3" /> {upCount} 转强
            </span>
          )}
          {downCount > 0 && (
            <span className={`flex items-center gap-1 font-medium ${negativeClass}`}>
              <ArrowDown className="h-3 w-3" /> {downCount} 转弱
            </span>
          )}
          {flatCount > 0 && (
            <span className={`flex items-center gap-1 ${isDark ? "text-gray-500" : "text-gray-400"}`}>
              <ArrowRight className="h-3 w-3" /> {flatCount} 持平
            </span>
          )}
        </div>
      </div>
      <div className="space-y-4">
        {CATEGORY_ORDER.map((cat) => {
          const catSignals = signals.filter((s) => s.category === cat);
          if (catSignals.length === 0) return null;
          return (
            <div key={cat}>
              <p className={`text-xs font-semibold mb-2 px-1 ${
                isDark ? "text-gray-400" : "text-gray-500"
              }`}>
                {CATEGORY_LABELS[cat] ?? cat}
              </p>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
                {catSignals.map((s) => (
                  <FactorSignalCard key={s.factor_id} signal={s} isDark={isDark} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Layer 3: Detail Report (always visible) + Share ─────────────

function ReportShareButton({ content, date, isDark }: { content: string; date: string; isDark: boolean }) {
  const [copied, setCopied] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const textWithAttribution = `${content}\n\n—— 来源：QuantGPT 因子研究日报 (quantgpt.online) | ${date}`;

  const copyText = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(textWithAttribution);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* fallback */
    }
  }, [textWithAttribution]);

  const drawCard = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const W = 800;
    const H = 1200;
    const dpr = 2;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    ctx.scale(dpr, dpr);

    // Background
    const grad = ctx.createLinearGradient(0, 0, W, H);
    grad.addColorStop(0, "#0f172a");
    grad.addColorStop(1, "#1e293b");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);

    // Accent bar
    ctx.fillStyle = "#3b82f6";
    ctx.fillRect(0, 0, 4, H);

    // Brand header
    ctx.fillStyle = "#94a3b8";
    ctx.font = "bold 16px -apple-system, system-ui, sans-serif";
    ctx.fillText("QuantGPT", 28, 36);
    ctx.fillStyle = "#475569";
    ctx.font = "13px -apple-system, system-ui, sans-serif";
    ctx.fillText("因子研究日报", 120, 36);
    ctx.textAlign = "right";
    ctx.fillText(date, W - 28, 36);
    ctx.textAlign = "left";

    // Divider
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(28, 52);
    ctx.lineTo(W - 28, 52);
    ctx.stroke();

    // Render markdown as plain text lines
    const plain = content
      .replace(/^#{1,3}\s+/gm, "")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/\*(.*?)\*/g, "$1")
      .replace(/^[-•]\s*/gm, "· ")
      .replace(/^\d+\.\s*/gm, (m) => m)
      .replace(/^>\s*/gm, "  ")
      .replace(/---/g, "");

    const lines = plain.split("\n");
    const lineHeight = 18;
    const maxLines = Math.floor((H - 90) / lineHeight);
    let y = 72;

    ctx.fillStyle = "#cbd5e1";
    ctx.font = "13px -apple-system, system-ui, sans-serif";

    for (let i = 0; i < Math.min(lines.length, maxLines); i++) {
      const line = lines[i].trim();
      if (!line) {
        y += 8;
        continue;
      }
      // Word wrap at width
      const maxWidth = W - 56;
      const words = line.split("");
      let current = "";
      for (const char of words) {
        if (ctx.measureText(current + char).width > maxWidth) {
          ctx.fillText(current, 28, y);
          y += lineHeight;
          current = char;
          if (y > H - 50) break;
        } else {
          current += char;
        }
      }
      if (current && y <= H - 50) {
        ctx.fillText(current, 28, y);
        y += lineHeight;
      }
      if (y > H - 50) break;
    }

    // Footer
    ctx.fillStyle = "#475569";
    ctx.font = "11px -apple-system, system-ui, sans-serif";
    ctx.fillText("来源：QuantGPT 因子研究日报", 28, H - 20);
    ctx.textAlign = "right";
    ctx.fillText("quantgpt.online", W - 28, H - 20);
    ctx.textAlign = "left";
  }, [content, date]);

  const openModal = useCallback(() => {
    setShowModal(true);
    requestAnimationFrame(drawCard);
  }, [drawCard]);

  const downloadImage = useCallback(() => {
    if (!canvasRef.current) return;
    const link = document.createElement("a");
    link.download = `quantgpt-daily-${date}.png`;
    link.href = canvasRef.current.toDataURL("image/png");
    link.click();
  }, [date]);

  const copyImage = useCallback(async () => {
    if (!canvasRef.current) return;
    try {
      const blob = await new Promise<Blob>((resolve) =>
        canvasRef.current!.toBlob((b) => resolve(b!), "image/png")
      );
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      downloadImage();
    }
  }, [downloadImage]);

  return (
    <>
      <div className="flex items-center gap-2">
        <button
          onClick={copyText}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            isDark ? "text-gray-400 bg-gray-800 hover:bg-gray-700" : "text-gray-600 bg-gray-50 hover:bg-gray-100"
          }`}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Share2 className="h-3.5 w-3.5" />}
          {copied ? "已复制" : "复制全文"}
        </button>
        <button
          onClick={openModal}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            isDark ? "text-gray-400 bg-gray-800 hover:bg-gray-700" : "text-gray-600 bg-gray-50 hover:bg-gray-100"
          }`}
        >
          <Download className="h-3.5 w-3.5" />
          分享图片
        </button>
      </div>

      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setShowModal(false)}
        >
          <div
            className={`${isDark ? "bg-gray-900" : "bg-white"} rounded-2xl shadow-2xl p-5 max-w-[850px] w-full mx-4 max-h-[90vh] overflow-y-auto`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className={`text-sm font-semibold ${isDark ? "text-gray-100" : "text-gray-900"}`}>分享日报</h3>
              <button
                onClick={() => setShowModal(false)}
                className={`p-1.5 rounded-lg text-gray-400 ${isDark ? "hover:text-gray-200 hover:bg-gray-800" : "hover:text-gray-600 hover:bg-gray-100"}`}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <canvas ref={canvasRef} className="w-full rounded-lg" />
            <div className="flex items-center gap-3 mt-4">
              <button
                onClick={copyImage}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
              >
                <Share2 className="h-4 w-4" />
                复制图片
              </button>
              <button
                onClick={downloadImage}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border ${isDark ? "border-gray-700 text-gray-300 hover:bg-gray-800" : "border-gray-200 text-gray-700 hover:bg-gray-50"} text-sm`}
              >
                <Download className="h-4 w-4" />
                下载
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/** Custom renderer: match the reference image typography */
function HighlightedMarkdown({ content, isDark }: { content: string; isDark: boolean }) {
  const textColor = isDark ? "text-gray-300" : "text-gray-700";
  const strongColor = isDark ? "text-gray-100" : "text-gray-900";

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h1 className={`text-xl font-bold mb-5 pb-3 border-b ${isDark ? "border-gray-700 text-gray-100" : "border-gray-200 text-gray-900"}`}>
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className={`text-lg font-bold mt-10 mb-4 pb-2 border-b ${isDark ? "border-gray-700 text-gray-100" : "border-gray-300 text-gray-900"}`}>
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className={`text-base font-bold mt-7 mb-3 ${isDark ? "text-gray-200" : "text-gray-800"}`}>
            {children}
          </h3>
        ),
        p: ({ children }) => (
          <p className={`text-sm leading-[1.9] my-3 ${textColor}`}>{children}</p>
        ),
        strong: ({ children }) => (
          <strong className={`font-semibold ${strongColor}`}>{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic">{children}</em>
        ),
        ul: ({ children }) => (
          <ul className="my-3 pl-5 list-disc space-y-2">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="my-3 pl-5 list-decimal space-y-2">{children}</ol>
        ),
        li: ({ children }) => (
          <li className={`text-sm leading-[1.9] ${textColor}`}>{children}</li>
        ),
        blockquote: ({ children }) => (
          <blockquote className={`border-l-2 pl-4 my-4 ${isDark ? "border-gray-600" : "border-gray-300"}`}>
            {children}
          </blockquote>
        ),
        hr: () => (
          <hr className={`my-8 ${isDark ? "border-gray-700" : "border-gray-200"}`} />
        ),
        a: ({ children, href }) => (
          <a href={href} className={`underline ${isDark ? "text-blue-400" : "text-blue-600"}`} target="_blank" rel="noopener noreferrer">{children}</a>
        ),
        code: ({ children }) => (
          <code className={`text-xs px-1.5 py-0.5 rounded ${isDark ? "bg-gray-800 text-amber-300" : "bg-gray-100 text-gray-800"}`}>{children}</code>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function DetailReport({ content, date, isDark }: { content: string; date: string; isDark: boolean }) {
  return (
    <div className={`rounded-xl border overflow-hidden ${
      isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"
    }`}>
      {/* Header with share buttons */}
      <div className={`flex items-center justify-between px-6 py-3 border-b ${
        isDark ? "border-gray-800" : "border-gray-100"
      }`}>
        <span className={`text-sm font-medium ${isDark ? "text-gray-300" : "text-gray-600"}`}>
          详细分析报告
        </span>
        <ReportShareButton content={content} date={date} isDark={isDark} />
      </div>
      {/* Always-visible markdown content */}
      <div className="px-6 py-5 max-w-none">
        <HighlightedMarkdown content={content} isDark={isDark} />
      </div>
      {/* Attribution footer */}
      <div className={`px-6 py-2.5 border-t text-[11px] ${
        isDark ? "border-gray-800 text-gray-500" : "border-gray-100 text-gray-400"
      }`}>
        来源：QuantGPT 因子研究日报 · quantgpt.online
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────

export default function DailySummary() {
  const { isDark } = useColorMode();
  const [list, setList] = useState<SummaryItem[]>([]);
  const [detail, setDetail] = useState<SummaryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setDetail(null);
    setSelectedDate(null);
    fetch(`/api/v1/daily-summaries?limit=30`)
      .then((r) => r.json())
      .then((data) => {
        const items = data.summaries ?? [];
        setList(items);
        if (items.length > 0) {
          setSelectedDate(items[0].date);
        }
      })
      .catch(() => setList([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedDate) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    fetch(`/api/v1/daily-summaries/${selectedDate}`)
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((data) => setDetail(data))
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, [selectedDate]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className={`h-6 w-6 animate-spin ${isDark ? "text-gray-500" : "text-gray-400"}`} />
      </div>
    );
  }

  if (list.length === 0) {
    return (
      <div className={`text-center py-20 ${isDark ? "text-gray-500" : "text-gray-400"}`}>
        <Calendar className="h-10 w-10 mx-auto mb-3 opacity-50" />
        <p className="text-sm">暂无盘后总结</p>
        <p className="text-xs mt-1">每个交易日 15:30 自动生成</p>
      </div>
    );
  }

  const metrics = detail?.metrics;
  const factorSignals = metrics?.factor_signals ?? [];

  return (
    <div className="flex gap-6">
      {/* Left: date list */}
      <div className={`w-44 shrink-0 rounded-xl border overflow-hidden ${
        isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"
      }`}>
        <div className={`px-4 py-3 text-xs font-medium border-b ${
          isDark ? "text-gray-300 border-gray-800" : "text-gray-600 border-gray-100"
        }`}>
          历史日报
        </div>
        <div className="max-h-[600px] overflow-y-auto">
          {list.map((item) => (
            <button
              key={item.date}
              onClick={() => setSelectedDate(item.date)}
              className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
                selectedDate === item.date
                  ? isDark
                    ? "bg-amber-500/10 text-amber-400 border-l-2 border-amber-500"
                    : "bg-blue-50 text-blue-700 border-l-2 border-blue-600"
                  : isDark
                    ? "text-gray-400 hover:bg-gray-800"
                    : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {item.date}
            </button>
          ))}
        </div>
      </div>

      {/* Right: 3-layer detail */}
      <div className="flex-1 min-w-0">
        {detailLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          </div>
        ) : detail ? (
          <div className="space-y-4">
            {/* Title + date */}
            <div className="flex items-center justify-between">
              <h2 className={`text-lg font-semibold ${isDark ? "text-gray-100" : "text-gray-900"}`}>
                {detail.title}
              </h2>
              <span className={`text-xs ${isDark ? "text-gray-500" : "text-gray-400"}`}>
                {detail.date}
              </span>
            </div>

            {/* Layer 1: Market State Card */}
            {metrics && <MarketStateCard metrics={metrics} isDark={isDark} />}

            {/* Index cards */}
            {metrics && (
              <div className="grid grid-cols-4 gap-3">
                <IndexCard label="沪深300" change={metrics.hs300_change ?? 0} isDark={isDark} />
                <IndexCard label="上证50" change={metrics.sz50_change ?? 0} isDark={isDark} />
                <IndexCard label="中证500" change={metrics.zz500_change ?? 0} isDark={isDark} />
                <IndexCard label="中证1000" change={metrics.csi1000_change ?? 0} isDark={isDark} />
              </div>
            )}

            {/* Layer 2: Factor Signal Panel (card grid) */}
            <FactorSignalPanel signals={factorSignals} isDark={isDark} />

            {/* Layer 3: Detail Report */}
            {detail.content && (
              <DetailReport content={detail.content} date={detail.date} isDark={isDark} />
            )}
          </div>
        ) : (
          <div className={`text-center py-20 ${isDark ? "text-gray-500" : "text-gray-400"}`}>
            <p className="text-sm">选择日期查看盘后总结</p>
          </div>
        )}
      </div>
    </div>
  );
}
