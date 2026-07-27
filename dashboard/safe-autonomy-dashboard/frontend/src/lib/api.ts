import type { Bootstrap, ControlIntent, User } from '../types'

const TOKEN_KEY = 'flight_dashboard_token'
export const getToken = () => sessionStorage.getItem(TOKEN_KEY)
export const setToken = (token: string | null) => token ? sessionStorage.setItem(TOKEN_KEY, token) : sessionStorage.removeItem(TOKEN_KEY)

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const response = await fetch(path, {
    ...init,
    headers: { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}), ...init.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `خطای سرویس (${response.status})`)
  }
  return response.json() as Promise<T>
}

export async function login(username: string, password: string) {
  const result = await api<{ access_token: string; role: string; display_name: string }>('/api/v1/auth/login', {
    method: 'POST', body: JSON.stringify({ username, password }),
  })
  setToken(result.access_token)
  return result
}

export const bootstrap = () => api<Bootstrap>('/api/v1/dashboard/bootstrap')
export const session = () => api<User>('/api/v1/session')
export const ackAlert = (id: string) => api(`/api/v1/alerts/${id}/ack`, { method: 'POST' })
export const createIntent = (action: string, reason: string) => api<ControlIntent>('/api/v1/control/intents', {
  method: 'POST', body: JSON.stringify({ action, reason, idempotency_key: crypto.randomUUID() }),
})
export const decideIntent = (id: string, decision: 'approve' | 'cancel') => api<ControlIntent>(`/api/v1/control/intents/${id}/${decision}`, {
  method: 'POST', body: JSON.stringify({ note: decision === 'approve' ? 'تأیید از پنل عملیات' : 'لغو از پنل عملیات' }),
})

