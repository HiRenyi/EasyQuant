import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface AdvancedSettingsValues {
  universe: string;
  start_date: string;
  end_date: string;
  n_groups: number;
  holding_period: number;
  benchmark: string;
  neutralize_industry: boolean;
  neutralize_cap: boolean;
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
        <div className="px-4 pb-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
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
                <option value="csi1000">中证1000</option>
                <option value="full_a">全A (最多2000只)</option>
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
                <option value="csi1000">中证1000</option>
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

          {/* Neutralization options */}
          <div className="border-t border-gray-100 pt-3">
            <p className="text-xs text-gray-500 mb-2">因子中性化</p>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={values.neutralize_industry}
                  onChange={(e) => set("neutralize_industry", e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500/20"
                />
                <span className="text-xs text-gray-600">行业中性</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={values.neutralize_cap}
                  onChange={(e) => set("neutralize_cap", e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500/20"
                />
                <span className="text-xs text-gray-600">市值中性</span>
              </label>
            </div>
            <p className="text-[10px] text-gray-400 mt-1">中性化可消除行业/市值偏暴露，获得更纯粹的因子 alpha</p>
          </div>
        </div>
      )}
    </div>
  );
}
