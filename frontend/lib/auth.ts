"use client";

// The JWT lives in an httpOnly cookie — the browser manages it automatically.
// We only keep non-secret display info (user_id, email) and the
// server-assigned session_id in localStorage.

export const USER_KEY = "ai_calendar_user";
export const SESSION_KEY = "ai_calendar_session_id";

export interface StoredUser {
  user_id: string;
  email: string;
}

export function getStoredUser(): StoredUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as StoredUser) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: StoredUser): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getStoredSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SESSION_KEY);
}

export function setStoredSessionId(sessionId: string): void {
  localStorage.setItem(SESSION_KEY, sessionId);
}

export function clearSession(): void {
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(SESSION_KEY);
}
