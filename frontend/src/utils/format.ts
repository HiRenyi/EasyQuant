/** Format a decimal as percentage string, e.g. 0.1234 -> "12.34%" */
export function pct(n: number): string {
  return (n * 100).toFixed(2) + "%";
}

/** Format a number to 4 decimal places */
export function num(n: number): string {
  return n.toFixed(4);
}
