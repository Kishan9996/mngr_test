import type { CalendarStatusResponse, ChatMessageResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function sendMessage(
  sessionId: string,
  message: string,
  timezone: string
): Promise<ChatMessageResponse> {
  const res = await fetch(`${API_URL}/api/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message, timezone }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `API error: ${res.status}`);
  }
  return res.json();
}

export async function getCalendarStatus(
  sessionId: string
): Promise<CalendarStatusResponse> {
  const res = await fetch(
    `${API_URL}/api/chat/status?session_id=${encodeURIComponent(sessionId)}`
  );
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
  return res.json();
}

export function getCalendarAuthUrl(
  provider: string,
  sessionId: string
): string {
  return `${API_URL}/api/calendar/auth/${provider}?session_id=${encodeURIComponent(sessionId)}`;
}

export async function disconnectCalendar(
  provider: string,
  sessionId: string
): Promise<void> {
  await fetch(
    `${API_URL}/api/calendar/disconnect/${provider}?session_id=${encodeURIComponent(sessionId)}`,
    { method: "DELETE" }
  );
}
