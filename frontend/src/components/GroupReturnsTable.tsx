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
  const groups = Object.entries(groupReturns).sort(([a], [b]) => a.localeCompare(b));

  if (groups.length === 0) return null;

  return (
    <div className="glass-card overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-subtle)]">
            <th className="px-4 py-3 text-left text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.15em] font-mono">
              分组
            </th>
            <th className="px-4 py-3 text-right text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.15em] font-mono">
              年化收益
            </th>
            <th className="px-4 py-3 text-right text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.15em] font-mono">
              Sharpe
            </th>
            <th className="px-4 py-3 text-right text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.15em] font-mono">
              最大回撤
            </th>
          </tr>
        </thead>
        <tbody>
          {groups.map(([key, g], i) => (
            <tr
              key={key}
              className="border-b border-[var(--border-subtle)] last:border-0 transition-colors hover:bg-[var(--bg-elevated)]/50"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <td className="px-4 py-3">
                <span className="font-mono text-xs font-semibold text-[var(--text-secondary)] px-2 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
                  {g.group}
                </span>
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums" style={{
                color: g.annual_return >= 0 ? 'var(--accent-green)' : 'var(--accent-red)',
              }}>
                {fmt(g.annual_return, true)}
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-[var(--text-primary)]">
                {fmt(g.sharpe)}
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-[var(--accent-red)]">
                {fmt(g.max_drawdown, true)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
