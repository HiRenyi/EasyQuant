import type { BacktestMetrics } from "../types/backtest";

const BASE = "";

function getAccessToken(): string | null {
  return localStorage.getItem("quantgpt_access_token");
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = { ...authHeaders(), ...options.headers };
  return fetch(url, { ...options, headers });
}

export interface SavedFactor {
  id: string;
  task_id: string | null;
  expression: string;
  name: string | null;
  note: string | null;
  tags: string[];
  metrics: BacktestMetrics | null;
  backtest_summary: Record<string, unknown> | null;
  params: Record<string, unknown> | null;
  report_url: string | null;
  created_at: string | null;
}

export interface SaveFactorPayload {
  task_id?: string;
  expression: string;
  name?: string;
  note?: string;
  tags?: string[];
  metrics?: Record<string, unknown>;
  backtest_summary?: Record<string, unknown>;
  params?: Record<string, unknown>;
  report_url?: string;
}

export async function saveFactor(payload: SaveFactorPayload): Promise<SavedFactor> {
  const res = await authFetch(`${BASE}/api/v1/factor-library`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `保存失败 (${res.status})`);
  }
  return res.json();
}

export async function fetchFactors(): Promise<SavedFactor[]> {
  const res = await authFetch(`${BASE}/api/v1/factor-library`);
  if (!res.ok) throw new Error(`获取因子库失败 (${res.status})`);
  const data = await res.json();
  return data.factors;
}

export async function updateFactor(
  factorId: string,
  updates: { name?: string; note?: string; tags?: string[] },
): Promise<SavedFactor> {
  const res = await authFetch(`${BASE}/api/v1/factor-library/${factorId}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(`更新失败 (${res.status})`);
  return res.json();
}

export async function deleteFactor(factorId: string): Promise<void> {
  const res = await authFetch(`${BASE}/api/v1/factor-library/${factorId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) throw new Error(`删除失败 (${res.status})`);
}
