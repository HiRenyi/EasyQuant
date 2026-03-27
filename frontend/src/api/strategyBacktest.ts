import { authFetch, parseError, BASE } from "./client";
import type { StrategyBacktestRequest } from "../types/strategy";

export async function submitStrategyBacktest(
  req: StrategyBacktestRequest,
): Promise<{ task_id: string; status: string }> {
  const res = await authFetch(`${BASE}/api/v1/strategy-backtest`, {
    method: "POST",
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
