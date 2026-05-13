"use client";

import { useEffect, useState } from "react";
import { CheckCircle, Link2, Unlink } from "lucide-react";
import { disconnectCalendar, getCalendarAuthUrl, getCalendarStatus } from "@/lib/api";

interface Props {
  sessionId: string;
  connectedProviders: string[];
  onProviderChange: (providers: string[]) => void;
}

const PROVIDERS = [
  {
    id: "google" as const,
    label: "Google Calendar",
    iconBg: "bg-red-100",
    iconText: "G",
    iconColor: "text-red-600",
  },
  {
    id: "outlook" as const,
    label: "Outlook Calendar",
    iconBg: "bg-blue-100",
    iconText: "O",
    iconColor: "text-blue-700",
  },
];

export function CalendarConnect({
  sessionId,
  connectedProviders,
  onProviderChange,
}: Props) {
  const [loading, setLoading] = useState<string | null>(null);

  // Poll calendar status every 3 s to pick up OAuth callbacks
  useEffect(() => {
    if (!sessionId) return;
    const id = setInterval(async () => {
      try {
        const status = await getCalendarStatus(sessionId);
        onProviderChange(status.connected_providers);
      } catch {
        // silently ignore — backend may not be ready yet
      }
    }, 3000);
    return () => clearInterval(id);
  }, [sessionId, onProviderChange]);

  async function handleConnect(provider: string) {
    if (!sessionId) return;
    // Open OAuth in the same tab; backend will redirect back to frontend
    window.location.href = getCalendarAuthUrl(provider, sessionId);
  }

  async function handleDisconnect(provider: string) {
    if (!sessionId) return;
    setLoading(provider);
    try {
      await disconnectCalendar(provider, sessionId);
      onProviderChange(connectedProviders.filter((p) => p !== provider));
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        Calendars
      </p>

      {PROVIDERS.map((p) => {
        const connected = connectedProviders.includes(p.id);
        const busy = loading === p.id;

        return (
          <div
            key={p.id}
            className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3 shadow-sm"
          >
            {/* Icon */}
            <div
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${p.iconBg}`}
            >
              <span className={`text-sm font-bold ${p.iconColor}`}>
                {p.iconText}
              </span>
            </div>

            {/* Label + status */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">
                {p.label}
              </p>
              <p
                className={`text-xs ${
                  connected ? "text-green-600" : "text-gray-400"
                }`}
              >
                {connected ? "Connected" : "Not connected"}
              </p>
            </div>

            {/* Action */}
            {connected ? (
              <button
                onClick={() => handleDisconnect(p.id)}
                disabled={busy}
                title="Disconnect"
                className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors disabled:opacity-50"
              >
                {busy ? (
                  <span className="h-4 w-4 block rounded-full border-2 border-gray-300 border-t-gray-600 animate-spin" />
                ) : (
                  <Unlink size={16} />
                )}
              </button>
            ) : (
              <button
                onClick={() => handleConnect(p.id)}
                disabled={busy}
                title="Connect"
                className="rounded-lg p-1.5 text-gray-400 hover:bg-green-50 hover:text-green-600 transition-colors disabled:opacity-50"
              >
                {busy ? (
                  <span className="h-4 w-4 block rounded-full border-2 border-gray-300 border-t-gray-600 animate-spin" />
                ) : (
                  <Link2 size={16} />
                )}
              </button>
            )}
          </div>
        );
      })}

      {connectedProviders.length > 0 && (
        <div className="flex items-center gap-1.5 text-xs text-green-600">
          <CheckCircle size={12} />
          <span>Ready to schedule</span>
        </div>
      )}
    </div>
  );
}
