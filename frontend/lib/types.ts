export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export interface ChatMessageRequest {
  session_id: string;
  message: string;
  timezone: string;
}

export interface ChatMessageResponse {
  session_id: string;
  response: string;
  connected_providers: string[];
}

export interface CalendarStatusResponse {
  session_id: string;
  connected_providers: string[];
}

export type CalendarProvider = "google" | "outlook";

export interface ConnectedCalendar {
  provider: CalendarProvider;
  label: string;
  icon: string;
}
