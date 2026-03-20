import { BarChart3 } from "lucide-react";

export default function Header() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-7xl px-6 py-4 flex items-center gap-3">
        <BarChart3 className="h-6 w-6 text-blue-600" />
        <div>
          <h1 className="text-lg font-semibold text-gray-900">QuantGPT</h1>
          <p className="text-sm text-gray-500">用自然语言描述你的因子策略，一键回测</p>
        </div>
      </div>
    </header>
  );
}
