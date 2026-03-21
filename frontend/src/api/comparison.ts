import { authFetch, parseError, BASE } from "./client";

export interface CompareFactorItem {
  expression: string;
  label?: string;
}

export interface FactorCompareMetrics {
  sharpe: number;
  ls_sharpe: number;
  annual_return: number;
  monotonicity: number;
  spread: number;
  ic_mean: number;
  rank_ic_mean: number;
  ic_ir: number;
  turnover: number;
}

export interface CumulativeReturnPoint {
  date: string;
  value: number;
}

export interface CompareFactorResult {
  expression: string;
  label: string;
  status: "success" | "failed";
  error?: string;
  metrics?: FactorCompareMetrics;
  cumulative_returns?: CumulativeReturnPoint[];
}

export interface CorrelationData {
  labels: string[];
  matrix: number[][];
}

export interface CompareFactorsResponse {
  factors: CompareFactorResult[];
  correlation: CorrelationData | null;
  params: {
    universe: string;
    start_date: string;
    end_date: string;
    n_groups: number;
    holding_period: number;
  };
}

export async function compareFactors(
  factors: CompareFactorItem[],
  params?: {
    universe?: string;
    start_date?: string;
    end_date?: string;
    n_groups?: number;
    holding_period?: number;
  },
): Promise<CompareFactorsResponse> {
  const res = await authFetch(`${BASE}/api/v1/compare-factors`, {
    method: "POST",
    body: JSON.stringify({ factors, ...params }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
