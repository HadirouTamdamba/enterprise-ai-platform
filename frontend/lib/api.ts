/** Typed API client with JWT handling and automatic refresh. */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("eap_access_token");
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("eap_access_token", access);
  localStorage.setItem("eap_refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("eap_access_token");
  localStorage.removeItem("eap_refresh_token");
}

async function tryRefresh(): Promise<boolean> {
  const refresh = localStorage.getItem("eap_refresh_token");
  if (!refresh) return false;
  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return true;
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  retried = false,
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) ?? {}),
  };
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401 && !retried) {
    if (await tryRefresh()) {
      return api<T>(path, options, true);
    }
    // Session is no longer recoverable — send the user back to login.
    clearTokens();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.code ?? "error", body.message ?? res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function login(email: string, password: string) {
  const form = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.code ?? "error", body.message ?? "Login failed");
  }
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}
