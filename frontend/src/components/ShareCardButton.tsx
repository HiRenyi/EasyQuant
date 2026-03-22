import { useRef, useState, useCallback } from "react";
import { Share2, Download, X } from "lucide-react";
import type { BacktestResult } from "../types/backtest";

interface Props {
  result: BacktestResult;
}

function drawShareCard(canvas: HTMLCanvasElement, result: BacktestResult) {
  const ctx = canvas.getContext("2d")!;
  const W = 640;
  const H = 340;
  const dpr = 2;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width = W + "px";
  canvas.style.height = H + "px";
  ctx.scale(dpr, dpr);

  // Background gradient
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, "#0f172a");
  grad.addColorStop(1, "#1e293b");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // Decorative accent bar
  ctx.fillStyle = "#3b82f6";
  ctx.fillRect(0, 0, 4, H);

  // Brand
  ctx.fillStyle = "#94a3b8";
  ctx.font = "bold 13px -apple-system, system-ui, sans-serif";
  ctx.fillText("QuantGPT", 24, 36);
  ctx.fillStyle = "#475569";
  ctx.font = "11px -apple-system, system-ui, sans-serif";
  ctx.fillText("AI 量化因子回测", 100, 36);

  // Expression
  ctx.fillStyle = "#60a5fa";
  ctx.font = "13px 'SF Mono', 'Menlo', monospace";
  const expr = result.params.expression;
  const maxExprLen = 70;
  const displayExpr = expr.length > maxExprLen ? expr.slice(0, maxExprLen) + "..." : expr;
  ctx.fillText(displayExpr, 24, 70);

  // Divider
  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(24, 86);
  ctx.lineTo(W - 24, 86);
  ctx.stroke();

  // Core metrics — strategy performance focused
  const m = result.metrics;
  const benchCagr = m.benchmark_cagr ?? null;
  const excessReturn = benchCagr != null ? m.cagr - benchCagr : null;

  const metrics = [
    { label: "策略总收益", value: (m.total_return * 100).toFixed(2) + "%", color: m.total_return >= 0 ? "#4ade80" : "#f87171" },
    { label: "策略年化", value: (m.cagr * 100).toFixed(2) + "%", color: m.cagr >= 0 ? "#4ade80" : "#f87171" },
    { label: "Sharpe", value: m.sharpe.toFixed(2), color: m.sharpe >= 1 ? "#4ade80" : m.sharpe >= 0.5 ? "#fbbf24" : "#e2e8f0" },
    { label: "最大回撤", value: (m.max_drawdown * 100).toFixed(2) + "%", color: "#f87171" },
    { label: "Sortino", value: m.sortino.toFixed(2), color: m.sortino >= 1.5 ? "#4ade80" : "#e2e8f0" },
    { label: "胜率", value: (m.win_rate * 100).toFixed(1) + "%", color: m.win_rate >= 0.55 ? "#4ade80" : "#e2e8f0" },
    { label: "波动率", value: (m.volatility * 100).toFixed(2) + "%", color: "#e2e8f0" },
    { label: "盈亏比", value: m.profit_factor.toFixed(2), color: m.profit_factor >= 1.5 ? "#4ade80" : "#e2e8f0" },
  ];

  const cols = 4;
  const cellW = (W - 48) / cols;
  const cellH = 64;
  const startY = 106;

  metrics.forEach((metric, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = 24 + col * cellW;
    const y = startY + row * cellH;

    ctx.fillStyle = "#94a3b8";
    ctx.font = "11px -apple-system, system-ui, sans-serif";
    ctx.fillText(metric.label, x, y);

    ctx.fillStyle = metric.color;
    ctx.font = "bold 22px -apple-system, system-ui, sans-serif";
    ctx.fillText(metric.value, x, y + 28);
  });

  // Excess return highlight
  const excessY = startY + 2 * cellH + 16;
  if (excessReturn != null && benchCagr != null) {
    // Benchmark line
    ctx.fillStyle = "#64748b";
    ctx.font = "11px -apple-system, system-ui, sans-serif";
    ctx.fillText(`基准年化 ${(benchCagr * 100).toFixed(2)}%`, 24, excessY);

    // Excess badge
    const badgeX = 200;
    const badgeText = `超额收益 ${excessReturn >= 0 ? "+" : ""}${(excessReturn * 100).toFixed(2)}%`;
    const badgeColor = excessReturn >= 0 ? "#22c55e" : "#ef4444";
    const badgeBg = excessReturn >= 0 ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)";

    ctx.fillStyle = badgeBg;
    const tw = ctx.measureText(badgeText).width;
    ctx.beginPath();
    ctx.roundRect(badgeX, excessY - 12, tw + 16, 18, 4);
    ctx.fill();

    ctx.fillStyle = badgeColor;
    ctx.font = "bold 12px -apple-system, system-ui, sans-serif";
    ctx.fillText(badgeText, badgeX + 8, excessY);
  }

  // Footer
  ctx.fillStyle = "#475569";
  ctx.font = "10px -apple-system, system-ui, sans-serif";
  const footer = `${result.params.universe.toUpperCase()} · ${result.params.start_date} ~ ${result.params.end_date} · ${result.params.holding_period}天持仓 · ${result.params.stock_count}只股票`;
  ctx.fillText(footer, 24, H - 20);

  ctx.fillStyle = "#64748b";
  ctx.textAlign = "right";
  ctx.fillText("quantgpt.online", W - 24, H - 20);
  ctx.textAlign = "left";
}

export default function ShareCardButton({ result }: Props) {
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
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 transition-colors"
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
            className="bg-white rounded-2xl shadow-2xl p-5 max-w-[700px] w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-900">分享回测结果</h3>
              <button
                onClick={() => setShowModal(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <canvas
              ref={canvasRef}
              className="w-full rounded-lg"
            />
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
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-700 hover:bg-gray-50"
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
