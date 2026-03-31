import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | undefined {
  return Cookies.get("al_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (res.status === 401) {
    Cookies.remove("al_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || "Request failed");
  }

  return res.json();
}

// Auth
export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  const data = await res.json();
  Cookies.set("al_token", data.access_token, { expires: 1 }); // 1 day
}

export function logout() {
  Cookies.remove("al_token");
  window.location.href = "/login";
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

// Reports
export const getTodayReport = () =>
  request<Record<string, any>>("/api/v1/reports/today");

export const getLast30Days = () =>
  request<Array<Record<string, any>>>("/api/v1/reports/last-30-days");

export const triggerReport = (sendEmail = false) =>
  request("/api/v1/reports/generate", {
    method: "POST",
    body: JSON.stringify({ send_email: sendEmail }),
  });

// Transactions
export const getTransactions = (params: Record<string, string> = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request<Record<string, any>>(`/api/v1/transactions/?${qs}`);
};

// QuickBooks
export const getQBStatus = () =>
  request<Record<string, any>>("/api/v1/quickbooks/status");

export const triggerSync = () =>
  request("/api/v1/quickbooks/sync", { method: "POST" });
