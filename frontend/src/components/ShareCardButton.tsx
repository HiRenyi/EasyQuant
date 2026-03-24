import { useRef, useState, useCallback } from "react";
import { Share2, Download, X } from "lucide-react";
import type { BacktestResult } from "../types/backtest";
import { useColorMode } from "../contexts/ColorModeContext";

interface Props {
  result: BacktestResult;
}

function drawShareCard(canvas: HTMLCanvasElement, result: BacktestResult) {
  const ctx = canvas.getContext("2d")!;
  const W = 640;
  const H = 420;
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

  // Brand
  ctx.fillStyle = "#94a3b8";
  ctx.font = "bold 13px -apple-system, system-ui, sans-serif";
  ctx.fillText("QuantGPT", 24, 32);
  ctx.fillStyle = "#475569";
  ctx.font = "11px -apple-system, system-ui, sans-serif";
  ctx.fillText("AI 量化因子回测", 100, 32);

  // Expression
  ctx.fillStyle = "#60a5fa";
  ctx.font = "13px 'SF Mono', 'Menlo', monospace";
  const expr = result.params.expression;
  const displayExpr = expr.length > 70 ? expr.slice(0, 70) + "..." : expr;
  ctx.fillText(displayExpr, 24, 58);

  // Divider
  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(24, 72);
  ctx.lineTo(W - 24, 72);
  ctx.stroke();

  // ---- NAV Curve (top section) ----
  const nav = result.nav_series;
  const chartX = 24;
  const chartY = 84;
  const chartW = W - 48;
  const chartH = 120;

  if (nav && nav.length >= 2) {
    const values = nav.map((p) => p.value);
    const minV = Math.min(...values) * 0.995;
    const maxV = Math.max(...values) * 1.005;
    const range = maxV - minV || 0.01;
    const finalVal = values[values.length - 1];
    const isUp = finalVal >= 1.0;
    const lineColor = isUp ? "#4ade80" : "#f87171";
    const fillColor = isUp ? "rgba(74,222,128,0.08)" : "rgba(248,113,113,0.08)";

    // Grid lines
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const gy = chartY + (chartH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(chartX, gy);
      ctx.lineTo(chartX + chartW, gy);
      ctx.stroke();
    }

    // Baseline at 1.0
    const baselineY = chartY + chartH - ((1.0 - minV) / range) * chartH;
    ctx.strokeStyle = "#475569";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(chartX, baselineY);
    ctx.lineTo(chartX + chartW, baselineY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Fill area
    ctx.beginPath();
    nav.forEach((p, i) => {
      const x = chartX + (i / (nav.length - 1)) * chartW;
      const y = chartY + chartH - ((p.value - minV) / range) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.lineTo(chartX + chartW, chartY + chartH);
    ctx.lineTo(chartX, chartY + chartH);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();

    // Line
    ctx.beginPath();
    nav.forEach((p, i) => {
      const x = chartX + (i / (nav.length - 1)) * chartW;
      const y = chartY + chartH - ((p.value - minV) / range) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Date labels
    ctx.fillStyle = "#475569";
    ctx.font = "10px -apple-system, system-ui, sans-serif";
    ctx.fillText(nav[0].date, chartX, chartY + chartH + 14);
    ctx.textAlign = "right";
    ctx.fillText(nav[nav.length - 1].date, chartX + chartW, chartY + chartH + 14);
    ctx.textAlign = "left";

    // Final NAV label
    ctx.fillStyle = lineColor;
    ctx.font = "bold 11px -apple-system, system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`NAV ${finalVal.toFixed(4)}`, chartX + chartW, chartY - 4);
    ctx.textAlign = "left";
  } else {
    // No NAV data — show placeholder
    ctx.fillStyle = "#334155";
    ctx.font = "12px -apple-system, system-ui, sans-serif";
    ctx.fillText("净值曲线暂无数据", chartX + chartW / 2 - 50, chartY + chartH / 2);
  }

  // ---- Metrics (below chart) ----
  const m = result.metrics;
  const benchCagr = m.benchmark_cagr ?? null;
  const excessReturn = benchCagr != null ? m.cagr - benchCagr : null;

  const metricsY = chartY + chartH + 34;

  // METRICS GRID
  const metrics = [
    { label: "总收益", value: (m.total_return * 100).toFixed(2) + "%", color: m.total_return >= 0 ? "#4ade80" : "#f87171" },
    { label: "年化收益", value: (m.cagr * 100).toFixed(2) + "%", color: m.cagr >= 0 ? "#4ade80" : "#f87171" },
    { label: "Sharpe", value: m.sharpe.toFixed(2), color: m.sharpe >= 1 ? "#4ade80" : m.sharpe >= 0.5 ? "#fbbf24" : "#e2e8f0" },
    { label: "最大回撤", value: (m.max_drawdown * 100).toFixed(2) + "%", color: "#f87171" },
    { label: "Sortino", value: m.sortino.toFixed(2), color: m.sortino >= 1.5 ? "#4ade80" : "#e2e8f0" },
    { label: "胜率", value: (m.win_rate * 100).toFixed(1) + "%", color: m.win_rate >= 0.55 ? "#4ade80" : "#e2e8f0" },
  ];

  const cols = 6;
  const cellW = (W - 48) / cols;

  metrics.forEach((metric, i) => {
    const x = 24 + i * cellW;
    ctx.fillStyle = "#64748b";
    ctx.font = "10px -apple-system, system-ui, sans-serif";
    ctx.fillText(metric.label, x, metricsY);
    ctx.fillStyle = metric.color;
    ctx.font = "bold 18px -apple-system, system-ui, sans-serif";
    ctx.fillText(metric.value, x, metricsY + 22);
  });

  // Excess return badge
  const badgeY = metricsY + 46;
  if (excessReturn != null && benchCagr != null) {
    ctx.fillStyle = "#64748b";
    ctx.font = "11px -apple-system, system-ui, sans-serif";
    ctx.fillText(`基准年化 ${(benchCagr * 100).toFixed(2)}%`, 24, badgeY);

    const badgeX = 180;
    const badgeText = `超额收益 ${excessReturn >= 0 ? "+" : ""}${(excessReturn * 100).toFixed(2)}%`;
    const badgeColor = excessReturn >= 0 ? "#22c55e" : "#ef4444";
    const badgeBg = excessReturn >= 0 ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)";

    ctx.fillStyle = badgeBg;
    const tw = ctx.measureText(badgeText).width;
    ctx.beginPath();
    ctx.roundRect(badgeX, badgeY - 12, tw + 16, 18, 4);
    ctx.fill();
    ctx.fillStyle = badgeColor;
    ctx.font = "bold 12px -apple-system, system-ui, sans-serif";
    ctx.fillText(badgeText, badgeX + 8, badgeY);
  }

  // Footer
  ctx.fillStyle = "#475569";
  ctx.font = "10px -apple-system, system-ui, sans-serif";
  const footer = `${result.params.universe.toUpperCase()} · ${result.params.start_date} ~ ${result.params.end_date} · ${result.params.holding_period}天持仓 · ${result.params.stock_count}只股票`;
  ctx.fillText(footer, 24, H - 16);
  ctx.fillStyle = "#64748b";
  ctx.textAlign = "right";
  ctx.fillText("quantgpt.online", W - 24, H - 16);
  ctx.textAlign = "left";
}

export default function ShareCardButton({ result }: Props) {
  const { isDark } = useColorMode();
  const [showModal, setShowModal] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const open = useCallback(() => {
    setShowModal(true);
    requestAnimationFrame(() => {
      if (canvasRef.current) drawShareCard(canvasRef.current, result);
    });
  }, [result]);

  const download = useCallback(() => {
    if (!canvasRef.current) return;
    const link = document.createElement("a");
    link.download = `quantgpt-${result.params.expression.slice(0, 20).replace(/[^a-zA-Z0-9]/g, "_")}.png`;
    link.href = canvasRef.current.toDataURL("image/png");
    link.click();
  }, [result]);

  const copyToClipboard = useCallback(async () => {
    if (!canvasRef.current) return;
    try {
      const blob = await new Promise<Blob>((resolve) =>
        canvasRef.current!.toBlob((b) => resolve(b!), "image/png")
      );
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      alert("已复制到剪贴板");
    } catch {
      download();
    }
  }, [download]);

  return (
    <>
      <button
        onClick={open}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium ${isDark ? "text-gray-400 bg-gray-800 hover:bg-gray-700" : "text-gray-600 bg-gray-50 hover:bg-gray-100"} transition-colors`}
      >
        <Share2 className="h-3.5 w-3.5" />
        分享
      </button>

      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setShowModal(false)}
        >
          <div
            className={`${isDark ? "bg-gray-900" : "bg-white"} rounded-2xl shadow-2xl p-5 max-w-[700px] w-full mx-4`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className={`text-sm font-semibold ${isDark ? "text-gray-100" : "text-gray-900"}`}>分享回测结果</h3>
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
                onClick={copyToClipboard}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
              >
                <Share2 className="h-4 w-4" />
                复制图片
              </button>
              <button
                onClick={download}
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
