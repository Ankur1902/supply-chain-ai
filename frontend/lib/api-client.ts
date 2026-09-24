import type { ApiError, ApiSuccess } from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001/api/v1";

const ACCESS_TOKEN_KEY = "asc_access_token";
const REFRESH_TOKEN_KEY = "asc_refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(access: string, refresh: string) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, access);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

export function clearTokens() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export class ApiRequestError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const body = (await res.json()) as ApiSuccess<{ access_token: string; refresh_token: string }>;
        setTokens(body.data.access_token, body.data.refresh_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined | null>;
  skipAuth?: boolean;
}

function buildUrl(path: string, params?: RequestOptions["params"]): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function request<T>(path: string, options: RequestOptions = {}, isRetry = false): Promise<T> {
  const { method = "GET", body, params, skipAuth = false } = options;
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (!skipAuth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(buildUrl(path, params), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !skipAuth && !isRetry) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return request<T>(path, options, true);
    }
    clearTokens();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new ApiRequestError(401, "NOT_AUTHENTICATED", "Session expired");
  }

  if (!res.ok) {
    let errBody: ApiError | null = null;
    try {
      errBody = await res.json();
    } catch {
      // ignore parse failure, fall through to generic error
    }
    throw new ApiRequestError(
      res.status,
      errBody?.error?.code ?? "UNKNOWN_ERROR",
      errBody?.error?.message ?? `Request failed with status ${res.status}`
    );
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const apiClient = {
  get: <T>(path: string, params?: RequestOptions["params"]) => request<T>(path, { method: "GET", params }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
