/** Typed API client for the QORA platform (/api/v1). */
export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const tok = {
  get access() { return localStorage.getItem("qora_access"); },
  set access(v: string | null) { v ? localStorage.setItem("qora_access", v) : localStorage.removeItem("qora_access"); },
  get refresh() { return localStorage.getItem("qora_refresh"); },
  set refresh(v: string | null) { v ? localStorage.setItem("qora_refresh", v) : localStorage.removeItem("qora_refresh"); },
};
export const tokens = tok;

async function api<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (tok.access) headers.Authorization = `Bearer ${tok.access}`;
  const res = await fetch(`/api/v1${path}`, { ...options, headers });
  if (res.status === 204) return undefined as T;

  let body: any = null;
  try { body = await res.json(); } catch { /* empty */ }

  if (!res.ok) {
    const err = body?.error ?? {};
    if (res.status === 401 && retry && tok.refresh && path !== "/auth/refresh") {
      const r = await fetch("/api/v1/auth/refresh", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tok.refresh }),
      });
      if (r.ok) {
        const t = await r.json();
        tok.access = t.access_token;
        tok.refresh = t.refresh_token;
        return api<T>(path, options, false);
      }
      tok.access = null; tok.refresh = null;
    }
    throw new ApiError(res.status, err.code ?? "ERROR", err.message ?? `Request failed (${res.status})`);
  }
  return body as T;
}

export const get = <T,>(p: string) => api<T>(p);
export const post = <T,>(p: string, d?: unknown) => api<T>(p, { method: "POST", body: d ? JSON.stringify(d) : undefined });
export const patch = <T,>(p: string, d: unknown) => api<T>(p, { method: "PATCH", body: JSON.stringify(d) });
export const del = <T,>(p: string) => api<T>(p, { method: "DELETE" });

// ---------- types ----------
export interface User { id: number; email: string; roles: string; account_status: string; created_at: string; }
export interface Conversation { id: number; active_service_id: number | null; active_journey_id: number | null; recovery_state: string; created_at: string; updated_at: string; }
export interface Msg {
  id: number; role: string; content: string; created_at: string;
  content_blocks: {
    permission_request?: { service_id: number; context_types: string[]; mode_options: string[] };
    suggestions?: Suggestion[];
    outcome?: { status: string; score: number; session_id: number; user_confirmation_required: boolean };
    deliverable?: { kind: string; status: string } | null;
    recovery?: { failure_type: string; recovery_action: string; options: string[]; detail: string };
  };
}
export interface Suggestion { service_id: number; title: string; summary: string; score: number; outcome: { success_rate: number; sessions: number }; followed: boolean; }
export interface IntentResult { primary_intent: string; secondary_intents: string[]; entities: Record<string, string>; required_capabilities: string[]; confidence: number; ambiguous: boolean; }
export interface SendResult {
  conversation_id: number;
  message: Msg;
  intent: IntentResult;
  service_match: { chosen_service_id: number | null; candidates: any[] };
  context_shared: Record<string, boolean>;
  service_response: { ok: boolean; deliverable: any; session_id: number | null };
  outcome: { status: string; score: number; session_id: number; user_confirmation_required: boolean } | null;
  trace_id: number;
  recovery: any;
}
export interface DiscoveryItem {
  service: { id: number; name: string; summary: string; category: string; risk_level: string };
  creator: { display_name: string; verification_status: string };
  outcome: { success_rate: number; sessions: number };
  trust: { overall: number; freshness: string };
  rank: { score: number; signals: Record<string, number> };
  followed: boolean;
}
export interface Memory { id: number; kind: string; subject: string; content: string; sensitivity: string; }
export interface Goal { id: number; title: string; status: string; }
export interface Journey { id: number; kind: string; state: any; }
export interface ContextSummary { memories: { kind: string; subject: string; content: string }[]; goals: { title: string; status: string }[]; journeys: { kind: string; state: any }[]; }

export const fmtScore = (n: number) => `${Math.round(n * 100)}%`;
