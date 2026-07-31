import { env } from '../config/env';

export type ApiError = {
  status: number;
  detail: unknown;
};

export type HttpClientOptions = RequestInit & {
  token?: string;
};

export async function httpClient<T>(path: string, options: HttpClientOptions = {}): Promise<T> {
  const { token, ...requestOptions } = options;
  const headers = new Headers(requestOptions.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...requestOptions,
    headers
  });

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw { status: response.status, detail } satisfies ApiError;
  }

  return response.json() as Promise<T>;
}

export function clientUuid(): string {
  if ('crypto' in window && 'randomUUID' in window.crypto) return window.crypto.randomUUID();
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
