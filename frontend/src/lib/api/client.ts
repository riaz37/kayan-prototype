/**
 * The console always calls its own `/api` proxy (see app/api/[...path]/route.ts),
 * which forwards to the backend server-side. That keeps the session cookie
 * first-party and avoids CORS entirely.
 */
export function apiBase(): string {
  return "/api";
}

/** True when the console talks to a backend on this machine (dev), false for a deployed one. */
export function isLocalApi(base = apiBase()): boolean {
  try {
    return ["localhost", "127.0.0.1", "[::1]"].includes(new URL(base).hostname);
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string | null,
  ) {
    super(detail ?? `Request failed with status ${status}`);
    this.name = "ApiError";
  }
}

const DEFAULT_TIMEOUT_MS = 20_000;

async function request<T>(path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(apiBase() + path, {
      ...rest,
      signal: rest.signal ?? controller.signal,
      headers: { Accept: "application/json", ...(rest.body ? { "Content-Type": "application/json" } : {}), ...rest.headers },
    });
    if (!res.ok) {
      let detail: string | null = null;
      try {
        const body = await res.json();
        detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown, opts?: { timeoutMs?: number }) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}), ...opts }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
};

/** SWR fetcher: keys are API paths. */
export const fetcher = <T>(path: string) => api.get<T>(path);
