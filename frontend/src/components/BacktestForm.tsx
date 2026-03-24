import { useState } from "react";
import { Send, Loader2 } from "lucide-react";
import type { BacktestRequest } from "../types/backtest";
import { useColorMode } from "../contexts/ColorModeContext";
import AdvancedSettings from "./AdvancedSettings";

interface Props {
  onSubmit: (req: BacktestRequest) => void;
  isLoading: boolean;
}

export default function BacktestForm({ onSubmit, isLoading }: Props) {
  const { isDark } = useColorMode();
  const [prompt, setPrompt] = useState("");
  const [settings, setSettings] = useState({
    universe: "hs300",
    start_date: "2023-01-01",
    end_date: "2025-12-31",
    n_groups: 5,
    holding_period: 5,
    benchmark: "hs300",
    neutralize_industry: true,
    neutralize_cap: true,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isLoading) return;
    onSubmit({ prompt: prompt.trim(), ...settings });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className={`rounded-xl border overflow-hidden transition-shadow ${
        isDark
          ? "border-gray-700 bg-gray-900 focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500"
          : "border-gray-200 bg-white focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500"
      }`}>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="描述你想测试的因子策略，例如：帮我测试一个20日动量因子"
          rows={3}
          className={`w-full px-4 pt-4 pb-2 text-sm resize-none focus:outline-none ${
            isDark
              ? "bg-gray-900 text-gray-100 placeholder:text-gray-500"
              : "placeholder:text-gray-400"
          }`}
        />
        <div className="px-4 pb-3 flex justify-end">
          <button
            type="submit"
            disabled={!prompt.trim() || isLoading}
            className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors bg-blue-600 hover:bg-blue-700"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            {isLoading ? "回测中..." : "开始回测"}
          </button>
        </div>
      </div>
      <AdvancedSettings values={settings} onChange={setSettings} />
    </form>
  );
}
