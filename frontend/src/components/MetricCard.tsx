interface MetricCardProps {
  label: string;
  value: string;
  color?: "default" | "green" | "red";
}

export default function MetricCard({ label, value, color = "default" }: MetricCardProps) {
  const valueColor =
    color === "green"
      ? "var(--accent-green)"
      : color === "red"
        ? "var(--accent-red)"
        : "var(--text-primary)";

  const glowStyle =
    color === "green"
      ? { boxShadow: '0 0 20px rgba(0, 255, 136, 0.06)' }
      : color === "red"
        ? { boxShadow: '0 0 20px rgba(255, 56, 96, 0.06)' }
        : {};

  return (
    <div
      className="glass-card p-4 transition-all duration-200 hover:border-[var(--border-hover)]"
      style={glowStyle}
    >
      <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.15em] font-mono">
        {label}
      </p>
      <p
        className="mt-2 text-xl font-bold tabular-nums tracking-tight"
        style={{ color: valueColor, fontFamily: "'JetBrains Mono', monospace" }}
      >
        {value}
      </p>
    </div>
  );
}
