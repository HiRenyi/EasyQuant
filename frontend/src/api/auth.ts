import type { User, LoginResponse } from "../types/auth";

const BASE = "";

export async function sendCode(email: string): Promise<{ message: string; expires_in: number }> {
  const res = await fetch(`${BASE}/api/v1/auth/send-code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `发送失败 (${res.status})`);
  }
  return res.json();
}

export async function verifyCode(email: string, code: string): Promise<LoginResponse> {
  const res = await fetch(`${BASE}/api/v1/auth/verify-code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `验证失败 (${res.status})`);
  }
  return res.json();
}

export async function refreshToken(refresh_token: string): Promise<{ access_token: string; token_type: string }> {
  const res = await fetch(`${BASE}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token }),
  });
  if (!res.ok) throw new Error("Token 刷新失败");
  return res.json();
}

export async function getMe(accessToken: string): Promise<User> {
  const res = await fetch(`${BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error("获取用户信息失败");
  return res.json();
}

export async function loginWithPassword(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `登录失败 (${res.status})`);
  }
  return res.json();
}

export async function setPassword(
  accessToken: string,
  password: string,
  oldPassword?: string,
): Promise<{ message: string; has_password: boolean }> {
  const res = await fetch(`${BASE}/api/v1/auth/set-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ password, old_password: oldPassword || null }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `设置失败 (${res.status})`);
  }
  return res.json();
}

export async function resetPassword(
  email: string,
  code: string,
  newPassword: string,
): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/api/v1/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code, new_password: newPassword }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `重置失败 (${res.status})`);
  }
  return res.json();
}
