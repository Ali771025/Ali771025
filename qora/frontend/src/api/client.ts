const API_BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  return localStorage.getItem("qora_token");
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem("qora_token", token);
  else localStorage.removeItem("qora_token");
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 204) return undefined as T;

  let body: any = null;
  try {
    body = await res.json();
  } catch {
    /* empty body */
  }

  if (!res.ok) {
    let message = body?.detail ?? body?.message ?? `Request failed (${res.status})`;
    if (Array.isArray(message)) {
      message = message.map((m: any) => m?.msg ?? JSON.stringify(m)).join(", ");
    }
    throw new ApiError(res.status, String(message));
  }
  return body as T;
}

export const get = <T,>(path: string) => api<T>(path);
export const post = <T,>(path: string, data?: unknown) =>
  api<T>(path, { method: "POST", body: data ? JSON.stringify(data) : undefined });
export const patch = <T,>(path: string, data: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(data) });
export const del = (path: string) => api<void>(path, { method: "DELETE" });

// ---------- helpers ----------
export const fmtMoney = (cents: number) =>
  (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });

export const initials = (name: string) =>
  name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
