import { authFetch, parseError, BASE } from "./client";

export interface PaperStrategy {
  id: string;
  name: string;
  expression: string;
  universe: string;
  holding_period: number;
  n_groups: number;
  initial_capital: number;
  current_value: number;
  total_return: number;
  status: "active" | "paused" | "stopped";
  last_rebalance_date: string | null;
  next_rebalance_date: string | null;
  source_task_id: string | null;
  created_at: string | null;
  nav_curve?: { date: string; value: number; daily_return: number | null }[];
}

export interface PaperOrder {
  id: string;
  date: string;
  stock_code: string;
  direction: "buy" | "sell";
  shares: number;
  price: number;
  amount: number;
  commission: number;
}

export async function createPaperStrategy(params: {
  expression: string;
  name?: string;
  universe?: string;
  holding_period?: number;
  n_groups?: number;
  initial_capital?: number;
  source_task_id?: string;
}): Promise<PaperStrategy> {
  const res = await authFetch(`${BASE}/api/v1/paper/strategies`, {
    method: "POST",
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchPaperStrategies(): Promise<PaperStrategy[]> {
  const res = await authFetch(`${BASE}/api/v1/paper/strategies`);
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return data.strategies;
}

export async function fetchPaperStrategy(id: string): Promise<PaperStrategy> {
  const res = await authFetch(`${BASE}/api/v1/paper/strategies/${id}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchPaperOrders(id: string, page = 1): Promise<{ orders: PaperOrder[]; total: number }> {
  const res = await authFetch(`${BASE}/api/v1/paper/strategies/${id}/orders?page=${page}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function updatePaperStrategy(id: string, status: string): Promise<PaperStrategy> {
  const res = await authFetch(`${BASE}/api/v1/paper/strategies/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
