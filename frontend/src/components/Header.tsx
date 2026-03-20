import { Activity } from "lucide-react";

export default function Header() {
  return (
    <header className="border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)]/80 backdrop-blur-md sticky top-0 z-50">
      <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Logo mark */}
          <div className="relative">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[var(--accent-green)] to-[var(--accent-cyan)] flex items-center justify-center">
              <Activity className="h-5 w-5 text-[var(--bg-primary)]" strokeWidth={2.5} />
            </div>
            <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-[var(--accent-green)] border-2 border-[var(--bg-secondary)]" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-[var(--text-primary)]">
              Quant<span className="gradient-text">GPT</span>
            </h1>
            <p className="text-[11px] text-[var(--text-muted)] tracking-wide uppercase">
              A 股因子回测引擎
            </p>
          </div>
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--bg-primary)] border border-[var(--border-subtle)]">
          <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-green)] animate-pulse" />
          <span className="text-[11px] text-[var(--text-muted)] font-medium tracking-wide">
            LIVE
          </span>
        </div>
      </div>
    </header>
  );
}
