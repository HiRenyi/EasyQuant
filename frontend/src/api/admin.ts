const BASE = "";
const ADMIN_TOKEN_KEY = "quantgpt_admin_token";

function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}

function adminHeaders(): Record<string, string> {
  const token = getAdminToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function adminFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = { ...adminHeaders(), ...options.headers };
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401 || res.status === 403) {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    window.location.href = "/admin/login";
  }
  return res;
}

export async function adminLogin(password: string): Promise<{ token: string }> {
  const res = await fetch(`${BASE}/api/v1/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `登录失败 (${res.status})`);
  }
  const data = await res.json();
  localStorage.setItem(ADMIN_TOKEN_KEY, data.token);
  return data;
}

export function adminLogout() {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
  window.location.href = "/admin/login";
}

export function isAdminLoggedIn(): boolean {
  return !!localStorage.getItem(ADMIN_TOKEN_KEY);
}

export interface Overview {
  user_count: number;
  task_count: number;
  success_rate: number;
  today_active: number;
  feedback_count: number;
  unresolved_feedback_count: number;
  status_distribution: { name: string; value: number }[];
  daily_tasks: { date: string; count: number }[];
  user_trend: { date: string; new_users: number; total_users: number }[];
}

export async function fetchOverview(): Promise<Overview> {
  const res = await adminFetch(`${BASE}/api/v1/admin/overview`);
  if (!res.ok) throw new Error("获取总览数据失败");
  return res.json();
}

export interface AdminUser {
  id: string;
  email: string;
  nickname: string | null;
  is_active: boolean;
  task_count: number;
  created_at: string | null;
  last_login_at: string | null;
}

export async function fetchUsers(page = 1, pageSize = 20): Promise<{ users: AdminUser[]; total: number; page: number; page_size: number }> {
  const res = await adminFetch(`${BASE}/api/v1/admin/users?page=${page}&page_size=${pageSize}`);
  if (!res.ok) throw new Error("获取用户列表失败");
  return res.json();
}

export interface AdminTask {
  id: string;
  user_email: string;
  user_id: string;
  status: string;
  expression: string | null;
  error: string | null;
  created_at: string | null;
}

export async function fetchTasks(
  page = 1,
  pageSize = 20,
  filters?: { status?: string; user_id?: string },
): Promise<{ tasks: AdminTask[]; total: number; page: number; page_size: number }> {
  let url = `${BASE}/api/v1/admin/tasks?page=${page}&page_size=${pageSize}`;
  if (filters?.status) url += `&status=${filters.status}`;
  if (filters?.user_id) url += `&user_id=${filters.user_id}`;
  const res = await adminFetch(url);
  if (!res.ok) throw new Error("获取任务列表失败");
  return res.json();
}

export interface AdminFeedback {
  id: string;
  user_email: string;
  description: string;
  screenshot_path: string | null;
  task_id: string | null;
  resolved: boolean;
  resolved_at: string | null;
  created_at: string | null;
}

export async function fetchFeedbacks(page = 1, pageSize = 20): Promise<{ feedbacks: AdminFeedback[]; total: number; page: number; page_size: number }> {
  const res = await adminFetch(`${BASE}/api/v1/admin/feedbacks?page=${page}&page_size=${pageSize}`);
  if (!res.ok) throw new Error("获取反馈列表失败");
  return res.json();
}

export async function resolveFeedback(id: string): Promise<void> {
  const res = await adminFetch(`${BASE}/api/v1/admin/feedbacks/${id}/resolve`, {
    method: "PATCH",
  });
  if (!res.ok) throw new Error("标记失败");
}
