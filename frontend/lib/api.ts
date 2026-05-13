import { clearToken, getToken } from "./auth";
import type { AuthResponse, CalendarStatusResponse, ChatMessageResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── HTTP helpers ──────────────────────────────────────────────────────────────

function authHeaders(): HeadersInit {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    clearToken();
    window.location.reload();
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `API error: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function apiRegister(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<AuthResponse>(res);
}

export async function apiLogin(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<AuthResponse>(res);
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export async function sendMessage(
  sessionId: string,
  message: string,
  timezone: string
): Promise<ChatMessageResponse> {
  const res = await fetch(`${API_URL}/api/chat/message`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ session_id: sessionId, message, timezone }),
  });
  return handleResponse<ChatMessageResponse>(res);
}

export async function getCalendarStatus(
  sessionId: string
): Promise<CalendarStatusResponse> {
  const res = await fetch(
    `${API_URL}/api/chat/status?session_id=${encodeURIComponent(sessionId)}`,
    { headers: authHeaders() }
  );
  return handleResponse<CalendarStatusResponse>(res);
}

// ── Calendar OAuth ────────────────────────────────────────────────────────────

export function getCalendarAuthUrl(provider: string, sessionId: string): string {
  const token = getToken();
  // Pass the JWT as a query param so the redirect carries auth through the browser navigation
  return `${API_URL}/api/calendar/auth/${provider}?session_id=${encodeURIComponent(sessionId)}&token=${encodeURIComponent(token ?? "")}`;
}

export async function disconnectCalendar(provider: string, sessionId: string): Promise<void> {
  await fetch(
    `${API_URL}/api/calendar/disconnect/${provider}?session_id=${encodeURIComponent(sessionId)}`,
    { method: "DELETE", headers: authHeaders() }
  );
}
