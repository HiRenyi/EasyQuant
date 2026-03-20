import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

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
    <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
      >
        高级设置
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && (
        <div className="px-4 pb-4 grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs text-gray-500">股票池</span>
            <select
              value={values.universe}
              onChange={(e) => set("universe", e.target.value)}
              className="mt-1 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              <option value="small_scale">small_scale (5只)</option>
              <option value="hs300">沪深300</option>
              <option value="csi500">中证500</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-gray-500">基准指数</span>
            <select
              value={values.benchmark}
              onChange={(e) => set("benchmark", e.target.value)}
              className="mt-1 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              <option value="hs300">沪深300</option>
              <option value="zz500">中证500</option>
              <option value="sz50">上证50</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-gray-500">开始日期</span>
            <input
              type="date"
              value={values.start_date}
              onChange={(e) => set("start_date", e.target.value)}
              className="mt-1 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-500">结束日期</span>
            <input
              type="date"
              value={values.end_date}
              onChange={(e) => set("end_date", e.target.value)}
              className="mt-1 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-500">分组数量</span>
            <input
              type="number"
              min={2}
              max={20}
              value={values.n_groups}
              onChange={(e) => set("n_groups", Number(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-500">持仓周期 (交易日)</span>
            <input
              type="number"
              min={1}
              max={60}
              value={values.holding_period}
              onChange={(e) => set("holding_period", Number(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </label>
        </div>
      )}
    </div>
  );
}
