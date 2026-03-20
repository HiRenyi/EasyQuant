import { Download } from "lucide-react";
import { getReportUrl } from "../api/client";

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

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">QuantStats 详细报告</span>
        <a
          href={url}
          download
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Download className="h-4 w-4" />
          下载报告
        </a>
      </div>
      <iframe src={url} className="w-full h-[800px] border-0" title="Backtest Report" />
    </div>
  );
}
