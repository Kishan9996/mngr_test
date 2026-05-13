"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarDays, ExternalLink, RefreshCw } from "lucide-react";
import { getCalendarEvents } from "@/lib/api";
import type { CalendarEventItem } from "@/lib/types";

interface Props {
  sessionId: string;
  connectedProviders: string[];
}

const PROVIDER_STYLES: Record<string, { dot: string; badge: string; label: string }> = {
  google:  { dot: "bg-red-500",  badge: "bg-red-50 text-red-700 border-red-200",  label: "Google" },
  outlook: { dot: "bg-blue-500", badge: "bg-blue-50 text-blue-700 border-blue-200", label: "Outlook" },
};

export function BookingsView({ sessionId, connectedProviders }: Props) {
  const [events, setEvents] = useState<CalendarEventItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [daysAhead, setDaysAhead] = useState(30);

  const fetchEvents = useCallback(async () => {
    if (!sessionId || connectedProviders.length === 0) {
      setEvents([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getCalendarEvents(sessionId, daysAhead);
      setEvents(data.events);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load events.");
    } finally {
      setLoading(false);
    }
  }, [sessionId, connectedProviders.join(","), daysAhead]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  const grouped = groupByDate(events);
  const dateKeys = Object.keys(grouped).sort();

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Show next</span>
          {[7, 14, 30, 60].map((d) => (
            <button
              key={d}
              onClick={() => setDaysAhead(d)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                daysAhead === d
                  ? "bg-brand-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
        <button
          onClick={fetchEvents}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {/* Empty states */}
        {connectedProviders.length === 0 && (
          <EmptyState
            icon={<CalendarDays size={32} className="text-gray-300" />}
            message="Connect a calendar from the sidebar to see your bookings."
          />
        )}

        {connectedProviders.length > 0 && !loading && events.length === 0 && !error && (
          <EmptyState
            icon={<CalendarDays size={32} className="text-gray-300" />}
            message={`No events found in the next ${daysAhead} days.`}
          />
        )}

        {error && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading && events.length === 0 && (
          <div className="flex flex-col gap-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 rounded-xl bg-gray-100 animate-pulse" />
            ))}
          </div>
        )}

        {/* Event list grouped by date */}
        {dateKeys.map((dateKey) => (
          <div key={dateKey} className="mb-6">
            <DateHeading dateKey={dateKey} />
            <div className="flex flex-col gap-2">
              {grouped[dateKey].map((event) => (
                <EventCard key={`${event.provider}-${event.event_id}`} event={event} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DateHeading({ dateKey }: { dateKey: string }) {
  const date = new Date(dateKey + "T00:00:00");
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  let label: string;
  if (isSameDay(date, today)) label = "Today";
  else if (isSameDay(date, tomorrow)) label = "Tomorrow";
  else label = date.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });

  return (
    <div className="flex items-center gap-3 mb-2 mt-1">
      <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</span>
      <div className="flex-1 h-px bg-gray-200" />
    </div>
  );
}

function EventCard({ event }: { event: CalendarEventItem }) {
  const style = PROVIDER_STYLES[event.provider] ?? PROVIDER_STYLES.google;

  const startDate = new Date(event.start);
  const endDate = new Date(event.end);

  const timeLabel = event.is_all_day
    ? "All day"
    : `${fmt(startDate)} – ${fmt(endDate)}`;

  return (
    <div className="flex items-start gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm hover:border-gray-300 transition-colors group">
      {/* Provider dot */}
      <div className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${style.dot}`} />

      {/* Details */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{event.title}</p>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1">
          <span className="text-xs text-gray-500">{timeLabel}</span>
          <span className="text-gray-300 text-xs">·</span>
          <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded border ${style.badge}`}>
            {style.label}
          </span>
          <span className="text-xs text-gray-400 truncate max-w-[160px]">{event.calendar_name}</span>
        </div>
      </div>

      {/* Open in calendar */}
      {event.html_link && (
        <a
          href={event.html_link}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-0.5 shrink-0 rounded-lg p-1.5 text-gray-300 hover:text-brand-600 hover:bg-brand-50 transition-colors opacity-0 group-hover:opacity-100"
          title="Open in calendar"
        >
          <ExternalLink size={14} />
        </a>
      )}
    </div>
  );
}

function EmptyState({ icon, message }: { icon: React.ReactNode; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      {icon}
      <p className="text-sm text-gray-400 max-w-xs">{message}</p>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function groupByDate(events: CalendarEventItem[]): Record<string, CalendarEventItem[]> {
  const groups: Record<string, CalendarEventItem[]> = {};
  for (const event of events) {
    const key = new Date(event.start).toISOString().slice(0, 10);
    if (!groups[key]) groups[key] = [];
    groups[key].push(event);
  }
  return groups;
}

function fmt(date: Date): string {
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}
