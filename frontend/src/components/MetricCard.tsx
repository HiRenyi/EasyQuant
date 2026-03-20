interface MetricCardProps {
  label: string;
  value: string;
  color?: "default" | "green" | "red";
  sub?: string;
  subLabel?: string;
}

export default function MetricCard({ label, value, color = "default", sub, subLabel }: MetricCardProps) {
  const colorClass =
    color === "green"
      ? "text-emerald-600"
      : color === "red"
        ? "text-red-600"
        : "text-gray-900";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`mt-1 text-xl font-semibold ${colorClass}`}>{value}</p>
      {sub != null && (
        <p className="mt-1 text-xs text-gray-400">
          {subLabel ?? "基准"} <span className="font-medium text-gray-500">{sub}</span>
        </p>
      )}
    </div>
  );
}
