import { useState } from "react";
import { Zap, Loader2 } from "lucide-react";
import type { BacktestRequest } from "../types/backtest";
import AdvancedSettings from "./AdvancedSettings";

interface Props {
  onSubmit: (req: BacktestRequest) => void;
  isLoading: boolean;
}

export default function BacktestForm({ onSubmit, isLoading }: Props) {
  const [prompt, setPrompt] = useState("");
  const [settings, setSettings] = useState({
    universe: "hs300",
    start_date: "2022-01-01",
    end_date: "2024-12-31",
    n_groups: 5,
    holding_period: 5,
    benchmark: "hs300",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isLoading) return;
    onSubmit({ prompt: prompt.trim(), ...settings });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="glass-card overflow-hidden transition-all duration-300 focus-within:border-[var(--accent-green)]/40 focus-within:shadow-[var(--glow-green)]">
        {/* Top label bar */}
        <div className="px-4 pt-3 flex items-center gap-2">
          <span className="text-[10px] font-semibold text-[var(--accent-green)] uppercase tracking-[0.2em] font-mono">
            FACTOR.PROMPT
          </span>
          <div className="flex-1 h-px bg-[var(--border-subtle)]" />
        </div>

        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="描述你想测试的因子策略 — 例如：帮我测试一个20日动量因子"
          rows={3}
          className="w-full px-4 pt-3 pb-2 text-sm bg-transparent resize-none focus:outline-none text-[var(--text-primary)] placeholder:text-[var(--text-muted)] font-light leading-relaxed"
        />

        <div className="px-4 pb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <kbd className="text-[10px] text-[var(--text-muted)] border border-[var(--border-subtle)] rounded px-1.5 py-0.5 font-mono">
              ⌘ Enter
            </kbd>
            <span className="text-[10px] text-[var(--text-muted)]">提交</span>
          </div>

          <button
            type="submit"
            disabled={!prompt.trim() || isLoading}
            className="group inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              background: !prompt.trim() || isLoading
                ? 'var(--bg-elevated)'
                : 'linear-gradient(135deg, var(--accent-green), var(--accent-cyan))',
              color: !prompt.trim() || isLoading
                ? 'var(--text-muted)'
                : 'var(--bg-primary)',
              boxShadow: prompt.trim() && !isLoading
                ? '0 0 24px rgba(0, 255, 136, 0.2), 0 0 48px rgba(0, 212, 255, 0.1)'
                : 'none',
            }}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4 transition-transform group-hover:scale-110" />
            )}
            {isLoading ? "回测中…" : "开始回测"}
          </button>
        </div>
      </div>

      <AdvancedSettings values={settings} onChange={setSettings} />
    </form>
  );
}
