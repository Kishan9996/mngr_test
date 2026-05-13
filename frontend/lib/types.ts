export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface AuthResponse {
  token: string;
  user_id: string;
  email: string;
}

export interface UserPayload {
  user_id: string;
  email: string;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface ChatMessageRequest {
  session_id: string;
  message: string;
  timezone: string;
}

export interface ChatMessageResponse {
  session_id: string;
  response: string;
  connected_providers: string[];
  needs_reconnect_providers: string[];
}

export interface CalendarStatusResponse {
  session_id: string;
  connected_providers: string[];
}

export type CalendarProvider = "google" | "outlook";

// ── Profile ───────────────────────────────────────────────────────────────────

export interface UserProfile {
  work_start: string;               // "HH:MM"
  work_end: string;                 // "HH:MM"
  default_duration_minutes: number;
  timezone: string;
}

// ── Bookings list ─────────────────────────────────────────────────────────────

export interface CalendarEventItem {
  event_id: string;
  title: string;
  start: string;       // ISO 8601
  end: string;
  is_all_day: boolean;
  calendar_name: string;
  calendar_id: string;
  provider: CalendarProvider;
  html_link: string;
}

export interface CalendarEventsResponse {
  events: CalendarEventItem[];
  fetched_from: string[];
}
