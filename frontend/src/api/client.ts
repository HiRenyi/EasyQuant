import type { BacktestRequest, Task, Session } from "../types/backtest";

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
  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    // Try refresh
    const refreshTokenStr = localStorage.getItem("quantgpt_refresh_token");
    if (refreshTokenStr) {
      try {
        const refreshRes = await fetch(`${BASE}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshTokenStr }),
        });
        if (refreshRes.ok) {
          const { access_token } = await refreshRes.json();
          localStorage.setItem("quantgpt_access_token", access_token);
          // Retry original request
          const retryHeaders = { ...options.headers, "Content-Type": "application/json", Authorization: `Bearer ${access_token}` };
          return fetch(url, { ...options, headers: retryHeaders });
        }
      } catch { /* fall through */ }
    }
    // Refresh failed, redirect to login
    localStorage.removeItem("quantgpt_access_token");
    localStorage.removeItem("quantgpt_refresh_token");
    window.location.href = "/login";
  }

  return res;
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail || `请求失败 (${res.status})`;
  } catch {
    if (res.status === 429) return "请求过于频繁，请稍后再试";
    if (res.status === 503) return "服务繁忙，请稍后再试";
    return `请求失败 (${res.status})`;
  }
}

export async function submitBacktest(req: BacktestRequest, sessionId?: string): Promise<{ task_id: string; status: string }> {
  const body = sessionId ? { ...req, session_id: sessionId } : req;
  const res = await authFetch(`${BASE}/api/v1/auto_backtest`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getTask(taskId: string): Promise<Task> {
  const res = await authFetch(`${BASE}/api/v1/tasks/${taskId}`);
  if (!res.ok) throw new Error(`Task fetch failed: ${res.status}`);
  return res.json();
}

export function streamTask(
  taskId: string,
  onUpdate: (task: Task) => void,
  onDone: () => void,
  onError: (err: Event) => void,
): () => void {
  const token = getAccessToken();
  const url = `${BASE}/api/v1/tasks/${taskId}/stream${token ? `?token=${token}` : ""}`;
  const es = new EventSource(url);

  es.addEventListener("update", (e) => {
    const task: Task = JSON.parse(e.data);
    onUpdate(task);
  });

  es.addEventListener("done", () => {
    es.close();
    onDone();
  });

  es.addEventListener("error", (e) => {
    es.close();
    onError(e);
  });

  return () => es.close();
}

export function getReportUrl(reportUrl: string): string {
  const token = getAccessToken();
  const sep = reportUrl.includes("?") ? "&" : "?";
  return `${BASE}${reportUrl}${token ? `${sep}token=${token}` : ""}`;
}

export async function fetchTasks(page = 1, pageSize = 20, sessionId?: string): Promise<{ tasks: Task[]; page: number; page_size: number }> {
  let url = `${BASE}/api/v1/tasks?page=${page}&page_size=${pageSize}`;
  if (sessionId) url += `&session_id=${sessionId}`;
  const res = await authFetch(url);
  if (!res.ok) throw new Error(`Tasks fetch failed: ${res.status}`);
  return res.json();
}

export async function submitIteration(
  taskId: string,
  nCandidates = 5,
): Promise<{ task_id: string; status: string }> {
  const res = await authFetch(`${BASE}/api/v1/tasks/${taskId}/iterate`, {
    method: "POST",
    body: JSON.stringify({ n_candidates: nCandidates }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function selectCandidate(
  taskId: string,
  candidateIndex: number,
): Promise<Record<string, unknown>> {
  const res = await authFetch(`${BASE}/api/v1/tasks/${taskId}/select_candidate`, {
    method: "POST",
    body: JSON.stringify({ candidate_index: candidateIndex }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

// ---- Sessions ----

export async function createSession(name?: string): Promise<Session> {
  const res = await authFetch(`${BASE}/api/v1/sessions`, {
    method: "POST",
    body: JSON.stringify({ name: name ?? null }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchSessions(): Promise<{ sessions: Session[] }> {
  const res = await authFetch(`${BASE}/api/v1/sessions`);
  if (!res.ok) throw new Error(`Sessions fetch failed: ${res.status}`);
  return res.json();
}

export async function renameSession(sessionId: string, name: string): Promise<Session> {
  const res = await authFetch(`${BASE}/api/v1/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await authFetch(`${BASE}/api/v1/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) throw new Error(await parseError(res));
}

export interface FeedbackPayload {
  description: string;
  screenshot?: string | null;
  task_id?: string | null;
  page_url?: string | null;
  user_agent?: string | null;
}

export async function submitFeedback(payload: FeedbackPayload): Promise<{ id: string; status: string; webhook_sent: boolean }> {
  const res = await authFetch(`${BASE}/api/v1/feedback`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
