import { Download, ExternalLink } from "lucide-react";
import { getReportUrl } from "../api/client";

interface Props {
  reportUrl: string;
}

export default function ReportViewer({ reportUrl }: Props) {
  const url = getReportUrl(reportUrl);

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-amber)]" />
          <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide">
            QuantStats 报告
          </span>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-medium text-[var(--text-secondary)] bg-[var(--bg-elevated)] border border-[var(--border-subtle)] hover:border-[var(--border-hover)] transition-colors"
          >
            <ExternalLink className="h-3 w-3" />
            新窗口
          </a>
          <a
            href={url}
            download
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-semibold transition-all"
            style={{
              background: 'linear-gradient(135deg, var(--accent-green), var(--accent-cyan))',
              color: 'var(--bg-primary)',
            }}
          >
            <Download className="h-3 w-3" />
            下载
          </a>
        </div>
      </div>
      <iframe
        src={url}
        className="w-full h-[800px] border-0 bg-white"
        title="Backtest Report"
      />
    </div>
  );
}
