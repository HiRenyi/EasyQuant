import { useColorMode } from "../contexts/ColorModeContext";

interface GroupReturn {
  group: string;
  annual_return: number;
  sharpe: number;
  max_drawdown: number;
}

interface Props {
  groupReturns: Record<string, GroupReturn>;
}

function fmt(n: number, pct = false): string {
  if (pct) return (n * 100).toFixed(2) + "%";
  return n.toFixed(4);
}

export default function GroupReturnsTable({ groupReturns }: Props) {
  const { positiveClass, negativeClass, isDark } = useColorMode();
  const groups = Object.entries(groupReturns).sort(([a], [b]) => a.localeCompare(b));

  if (groups.length === 0) return null;

  return (
    <div className={`rounded-xl border ${isDark ? "border-gray-700" : "border-gray-200"} ${isDark ? "bg-gray-900" : "bg-white"} overflow-hidden`}>
      <table className="w-full text-sm">
        <thead>
          <tr className={`border-b ${isDark ? "border-gray-700" : "border-gray-100"} ${isDark ? "bg-gray-800/50" : "bg-gray-50/50"}`}>
            <th className={`px-4 py-3 text-left font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>分组</th>
            <th className={`px-4 py-3 text-right font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>年化收益</th>
            <th className={`px-4 py-3 text-right font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>Sharpe</th>
            <th className={`px-4 py-3 text-right font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>最大回撤</th>
          </tr>
        </thead>
        <tbody>
          {groups.map(([key, g]) => (
            <tr key={key} className={`border-b ${isDark ? "border-gray-800" : "border-gray-50"} last:border-0`}>
              <td className={`px-4 py-2.5 font-medium ${isDark ? "text-gray-300" : "text-gray-700"}`}>{g.group}</td>
              <td className={`px-4 py-2.5 text-right ${g.annual_return >= 0 ? positiveClass : negativeClass}`}>
                {fmt(g.annual_return, true)}
              </td>
              <td className={`px-4 py-2.5 text-right ${isDark ? "text-gray-300" : "text-gray-700"}`}>{fmt(g.sharpe)}</td>
              <td className={`px-4 py-2.5 text-right ${negativeClass}`}>{fmt(g.max_drawdown, true)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
