import { useColorMode } from "../contexts/ColorModeContext";

interface Props {
  labels: string[];
  matrix: number[][] | Record<string, Record<string, number>>;
}

/**
 * Shared correlation matrix table with color coding.
 * Accepts either a 2D array (from comparison API) or a nested dict (from attribution API).
 */
export default function CorrelationMatrix({ labels, matrix }: Props) {
  const { isDark } = useColorMode();

  // Normalize to getValue(row, col)
  const getValue = (rowIdx: number, colIdx: number): number => {
    if (Array.isArray(matrix)) {
      return matrix[rowIdx]?.[colIdx] ?? 0;
    }
    // Record<string, Record<string, number>>
    const rowLabel = labels[rowIdx];
    const colLabel = labels[colIdx];
    return (matrix as Record<string, Record<string, number>>)[rowLabel]?.[colLabel] ?? 0;
  };

  return (
    <div className="overflow-x-auto">
      <table className="text-xs">
        <thead>
          <tr>
            <th className="px-2 py-1" />
            {labels.map((l) => (
              <th key={l} className={`px-2 py-1 ${isDark ? "text-gray-400" : "text-gray-500"} font-normal truncate max-w-[80px]`}>
                {l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((row, ri) => (
            <tr key={row}>
              <td className={`px-2 py-1 ${isDark ? "text-gray-400" : "text-gray-500"} font-medium truncate max-w-[80px]`}>{row}</td>
              {labels.map((col, ci) => {
                const val = getValue(ri, ci);
                const abs = Math.abs(val);
                const bg =
                  ri === ci
                    ? isDark ? "bg-gray-800" : "bg-gray-100"
                    : abs > 0.5
                    ? isDark ? "bg-red-500/20 text-red-400" : "bg-red-100 text-red-700"
                    : abs > 0.3
                    ? isDark ? "bg-amber-500/10 text-amber-400" : "bg-amber-50 text-amber-700"
                    : isDark ? "text-gray-400" : "text-gray-600";
                return (
                  <td key={col} className={`px-2 py-1 text-center ${bg}`}>
                    {val.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
