import { useState } from "react";
import { ChevronDown, Settings2 } from "lucide-react";

interface AdvancedSettingsValues {
  universe: string;
  start_date: string;
  end_date: string;
  n_groups: number;
  holding_period: number;
  benchmark: string;
}

interface Props {
  values: AdvancedSettingsValues;
  onChange: (values: AdvancedSettingsValues) => void;
}

export default function AdvancedSettings({ values, onChange }: Props) {
  const [open, setOpen] = useState(false);

  const set = <K extends keyof AdvancedSettingsValues>(key: K, val: AdvancedSettingsValues[K]) =>
    onChange({ ...values, [key]: val });

  return (
    <div className="glass-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 flex items-center justify-between text-sm transition-colors hover:bg-[var(--bg-elevated)]/50"
      >
        <div className="flex items-center gap-2">
          <Settings2 className="h-3.5 w-3.5 text-[var(--text-muted)]" />
          <span className="text-[var(--text-secondary)] font-medium">高级设置</span>
        </div>
        <ChevronDown
          className={`h-4 w-4 text-[var(--text-muted)] transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div className="px-4 pb-4 grid grid-cols-2 gap-3 animate-fade-in border-t border-[var(--border-subtle)]">
          <div className="pt-3">
            <label className="block">
              <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider font-mono">
                股票池
              </span>
              <select
                value={values.universe}
                onChange={(e) => set("universe", e.target.value)}
                className="quant-select mt-1.5 block w-full px-3 py-2 text-sm"
              >
                <option value="small_scale">small_scale (5只)</option>
                <option value="hs300">沪深300</option>
                <option value="csi500">中证500</option>
              </select>
            </label>
          </div>
          <div className="pt-3">
            <label className="block">
              <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider font-mono">
                基准指数
              </span>
              <select
                value={values.benchmark}
                onChange={(e) => set("benchmark", e.target.value)}
                className="quant-select mt-1.5 block w-full px-3 py-2 text-sm"
              >
                <option value="hs300">沪深300</option>
                <option value="zz500">中证500</option>
                <option value="sz50">上证50</option>
              </select>
            </label>
          </div>
          <label className="block">
            <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider font-mono">
              开始日期
            </span>
            <input
              type="date"
              value={values.start_date}
              onChange={(e) => set("start_date", e.target.value)}
              className="quant-input mt-1.5 block w-full px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider font-mono">
              结束日期
            </span>
            <input
              type="date"
              value={values.end_date}
              onChange={(e) => set("end_date", e.target.value)}
              className="quant-input mt-1.5 block w-full px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider font-mono">
              分组数量
            </span>
            <input
              type="number"
              min={2}
              max={20}
              value={values.n_groups}
              onChange={(e) => set("n_groups", Number(e.target.value))}
              className="quant-input mt-1.5 block w-full px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider font-mono">
              持仓周期
            </span>
            <input
              type="number"
              min={1}
              max={60}
              value={values.holding_period}
              onChange={(e) => set("holding_period", Number(e.target.value))}
              className="quant-input mt-1.5 block w-full px-3 py-2 text-sm"
            />
          </label>
        </div>
      )}
    </div>
  );
}
