import { authFetch, parseError, BASE } from "./client";

export interface FactorItem {
  expression: string;
  weight: number;
  label?: string;
}

export interface CompositeBacktestPayload {
  factors: FactorItem[];
  combination_method: string;
  universe: string;
  start_date: string;
  end_date: string;
  n_groups: number;
  holding_period: number;
  benchmark: string;
  session_id?: string;
}

export interface CorrelationResult {
  labels: string[];
  matrix: number[][];
}

export async function submitCompositeBacktest(
  payload: CompositeBacktestPayload,
): Promise<{ task_id: string; status: string }> {
  const res = await authFetch(`${BASE}/api/v1/composite-backtest`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchFactorCorrelation(
  factors: FactorItem[],
  universe = "hs300",
  startDate = "2023-01-01",
  endDate = "2025-12-31",
): Promise<CorrelationResult> {
  const res = await authFetch(`${BASE}/api/v1/factor-correlation`, {
    method: "POST",
    body: JSON.stringify({
      factors,
      universe,
      start_date: startDate,
      end_date: endDate,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export interface AttributionPayload {
  factors: FactorItem[];
  composite_expression?: string;
  universe: string;
  start_date: string;
  end_date: string;
  n_groups: number;
  holding_period: number;
}

export interface AttributionFactor {
  expression: string;
  label: string;
  sharpe?: number;
  annual_return?: number;
  monotonicity?: number;
  spread?: number;
  ic_mean?: number;
  ic_ir?: number;
  turnover?: number;
  status: "success" | "failed";
  error?: string;
}

export interface AttributionContribution {
  label: string;
  marginal_ic: number;
  contribution_pct?: number;
}

export interface AttributionResult {
  factors: AttributionFactor[];
  ic_correlation: Record<string, Record<string, number>> | null;
  contributions: AttributionContribution[];
  composite: {
    expression: string;
    sharpe: number;
    annual_return: number;
    monotonicity: number;
    ic_mean: number;
  } | null;
}

export async function fetchFactorAttribution(
  payload: AttributionPayload,
): Promise<AttributionResult> {
  const res = await authFetch(`${BASE}/api/v1/factor-attribution`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
