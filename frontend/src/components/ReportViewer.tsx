import { useRef } from "react";
import { Download } from "lucide-react";
import { getReportUrl } from "../api/client";
import { useColorMode } from "../contexts/ColorModeContext";

interface Props {
  reportUrl: string;
}

function getAuthReportUrl(reportUrl: string): string {
  const url = getReportUrl(reportUrl);
  const token = localStorage.getItem("quantgpt_access_token");
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

export default function ReportViewer({ reportUrl }: Props) {
  const url = getAuthReportUrl(reportUrl);
  const { isDark } = useColorMode();
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const onIframeLoad = () => {
    if (!isDark) return;
    try {
      const doc = iframeRef.current?.contentDocument;
      if (!doc) return;
      const style = doc.createElement('style');
      style.textContent = `
        body { background: #111827 !important; color: #e5e7eb !important; }
        table { color: #d1d5db !important; border-color: #374151 !important; }
        th { background: #1f2937 !important; color: #f3f4f6 !important; border-color: #374151 !important; }
        td { border-color: #374151 !important; }
        tr:nth-child(even) { background: #1f2937 !important; }
        tr:nth-child(odd) { background: #111827 !important; }
        h1, h2, h3, h4, h5, h6 { color: #f9fafb !important; }
        a { color: #60a5fa !important; }
        .container, .row, div { background-color: inherit; }
        img { filter: invert(0.88) hue-rotate(180deg); }
      `;
      doc.head.appendChild(style);
    } catch (e) {
      // Cross-origin iframe, can't inject CSS
    }
  };

  return (
    <div className={`rounded-xl border ${isDark ? "border-gray-700 bg-gray-900" : "border-gray-200 bg-white"} overflow-hidden`}>
      <div className={`px-4 py-3 border-b ${isDark ? "border-gray-700" : "border-gray-100"} flex items-center justify-between`}>
        <span className={`text-sm font-medium ${isDark ? "text-gray-300" : "text-gray-700"}`}>QuantStats 详细报告</span>
        <a
          href={url}
          download
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Download className="h-4 w-4" />
          下载报告
        </a>
      </div>
      <iframe
        ref={iframeRef}
        src={url}
        className={`w-full h-[800px] border-0 ${isDark ? "bg-gray-900" : ""}`}
        title="Backtest Report"
        onLoad={onIframeLoad}
      />
    </div>
  );
}
