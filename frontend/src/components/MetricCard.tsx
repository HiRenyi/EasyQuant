import { useColorMode } from "../contexts/ColorModeContext";

interface MetricCardProps {
  label: string;
  value: string;
  color?: "default" | "green" | "red";
  sub?: string;
  subLabel?: string;
}

export default function MetricCard({ label, value, color = "default", sub, subLabel }: MetricCardProps) {
  const { positiveClass, negativeClass, isDark } = useColorMode();
  const colorClass =
    color === "green"
      ? positiveClass
      : color === "red"
        ? negativeClass
        : isDark ? "text-gray-100" : "text-gray-900";

  return (
    <div className={`rounded-xl border ${isDark ? "border-gray-700" : "border-gray-200"} ${isDark ? "bg-gray-900" : "bg-white"} p-4`}>
      <p className={`text-xs font-medium ${isDark ? "text-gray-400" : "text-gray-500"} uppercase tracking-wide`}>{label}</p>
      <p className={`mt-1 text-xl font-semibold ${colorClass}`}>{value}</p>
      {sub != null && (
        <p className={`mt-1 text-xs ${isDark ? "text-gray-500" : "text-gray-400"}`}>
          {subLabel ?? "基准"} <span className={`font-medium ${isDark ? "text-gray-400" : "text-gray-500"}`}>{sub}</span>
        </p>
      )}
    </div>
  );
}
