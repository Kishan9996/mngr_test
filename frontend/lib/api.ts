import { clearSession } from "./auth";
import type { CalendarEventsResponse, CalendarStatusResponse, ChatMessageResponse, UserProfile } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const BASE: RequestInit = { credentials: "include" };

// ── Response handlers ─────────────────────────────────────────────────────────

/**
 * Used by authenticated routes.
 * 401 means the session cookie expired → clear local state and reload.
 */
async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    clearSession();
    window.location.reload();
    throw new Error("Session expired. Please sign in again.");
  }
  if (res.status === 429) {
    throw new Error("Too many requests. Please wait a moment and try again.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

/**
 * Used by login / register only.
 * 401 here means wrong credentials — do NOT clear the session or reload.
 */
async function handleAuthResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    throw new Error("Invalid email or password.");
  }
  if (res.status === 409) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "An account with this email already exists.");
  }
  if (res.status === 429) {
    throw new Error("Too many attempts. Please wait a minute before trying again.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Something went wrong. Please try again.");
  }
  return res.json() as Promise<T>;
}

/** Wraps fetch to convert network errors into friendly messages. */
async function safeFetch(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch {
    throw new Error("Cannot reach the server. Check your connection and try again.");
  }
}

function json(body: unknown): RequestInit {
  return {
    ...BASE,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// ── Auth ──────────────────────────────────────────────────────────────────────

type AuthResult = { user_id: string; email: string; session_id: string };

export async function apiRegister(email: string, password: string): Promise<AuthResult> {
  const res = await safeFetch(`${API_URL}/api/auth/register`, json({ email, password }));
  return handleAuthResponse<AuthResult>(res);
}

export async function apiLogin(email: string, password: string): Promise<AuthResult> {
  const res = await safeFetch(`${API_URL}/api/auth/login`, json({ email, password }));
  return handleAuthResponse<AuthResult>(res);
}

export async function apiLogout(): Promise<void> {
  await safeFetch(`${API_URL}/api/auth/logout`, { ...BASE, method: "POST" });
}

export async function apiMe(): Promise<{ user_id: string; email: string; session_id: string } | null> {
  try {
    const res = await fetch(`${API_URL}/api/auth/me`, BASE);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export async function sendMessage(
  sessionId: string,
  message: string,
  timezone: string
): Promise<ChatMessageResponse> {
  const res = await safeFetch(`${API_URL}/api/chat/message`, json({ session_id: sessionId, message, timezone }));
  return handleResponse<ChatMessageResponse>(res);
}

export async function getCalendarStatus(sessionId: string): Promise<CalendarStatusResponse> {
  const res = await safeFetch(
    `${API_URL}/api/chat/status?session_id=${encodeURIComponent(sessionId)}`,
    BASE
  );
  return handleResponse<CalendarStatusResponse>(res);
}

export async function clearChatHistory(sessionId: string): Promise<void> {
  await safeFetch(
    `${API_URL}/api/chat/history?session_id=${encodeURIComponent(sessionId)}`,
    { ...BASE, method: "DELETE" }
  );
}

export async function getChatHistory(
  sessionId: string
): Promise<{ session_id: string; messages: { role: string; content: string }[] }> {
  const res = await safeFetch(
    `${API_URL}/api/chat/history?session_id=${encodeURIComponent(sessionId)}`,
    BASE
  );
  if (!res.ok) return { session_id: sessionId, messages: [] };
  return res.json();
}

// ── Profile ───────────────────────────────────────────────────────────────────

export async function getProfile(): Promise<UserProfile> {
  const res = await safeFetch(`${API_URL}/api/profile`, BASE);
  return handleResponse<UserProfile>(res);
}

export async function updateProfile(patch: Partial<UserProfile>): Promise<UserProfile> {
  const res = await safeFetch(`${API_URL}/api/profile`, {
    ...BASE,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return handleResponse<UserProfile>(res);
}

// ── Calendar OAuth ────────────────────────────────────────────────────────────

export function getCalendarAuthUrl(provider: string, sessionId: string): string {
  return `${API_URL}/api/calendar/auth/${provider}?session_id=${encodeURIComponent(sessionId)}`;
}

export async function disconnectCalendar(provider: string, sessionId: string): Promise<void> {
  await safeFetch(
    `${API_URL}/api/calendar/disconnect/${provider}?session_id=${encodeURIComponent(sessionId)}`,
    { ...BASE, method: "DELETE" }
  );
}

export async function getCalendarEvents(
  sessionId: string,
  daysAhead = 30,
  timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
): Promise<CalendarEventsResponse> {
  const params = new URLSearchParams({ session_id: sessionId, days_ahead: String(daysAhead), timezone });
  const res = await safeFetch(`${API_URL}/api/calendar/events?${params}`, BASE);
  return handleResponse<CalendarEventsResponse>(res);
}
