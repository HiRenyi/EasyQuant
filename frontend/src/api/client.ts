import type { BacktestRequest, Task } from "../types/backtest";

const BASE = "";

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

export async function submitBacktest(req: BacktestRequest): Promise<{ task_id: string; status: string }> {
  const res = await fetch(`${BASE}/api/v1/auto_backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getTask(taskId: string): Promise<Task> {
  const res = await fetch(`${BASE}/api/v1/tasks/${taskId}`);
  if (!res.ok) throw new Error(`Task fetch failed: ${res.status}`);
  return res.json();
}

export function streamTask(
  taskId: string,
  onUpdate: (task: Task) => void,
  onDone: () => void,
  onError: (err: Event) => void,
): () => void {
  const es = new EventSource(`${BASE}/api/v1/tasks/${taskId}/stream`);

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
  return `${BASE}${reportUrl}`;
}
