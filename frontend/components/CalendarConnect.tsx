"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, Link2, Unlink } from "lucide-react";
import { disconnectCalendar, getCalendarAuthUrl, getCalendarStatus } from "@/lib/api";

interface Props {
  sessionId: string;
  connectedProviders: string[];
  needsReconnect: string[];
  onProviderChange: (providers: string[]) => void;
  onDismissReconnect: (provider: string) => void;
}

const PROVIDERS = [
  { id: "google" as const, label: "Google Calendar", iconBg: "bg-red-100", iconText: "G", iconColor: "text-red-600" },
  { id: "outlook" as const, label: "Outlook Calendar", iconBg: "bg-blue-100", iconText: "O", iconColor: "text-blue-700" },
];

export function CalendarConnect({
  sessionId,
  connectedProviders,
  needsReconnect,
  onProviderChange,
  onDismissReconnect,
}: Props) {
  const [loading, setLoading] = useState<string | null>(null);

  // Fetch immediately on mount, then poll every 5 s only to catch OAuth callbacks.
  // The immediate fetch eliminates the visible "Not connected" flash on every refresh.
  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;

    async function check() {
      try {
        const status = await getCalendarStatus(sessionId);
        if (!cancelled) onProviderChange(status.connected_providers);
      } catch { /* ignore */ }
    }

    check(); // fire right away
    const id = setInterval(check, 5000); // then poll for OAuth return
    return () => { cancelled = true; clearInterval(id); };
  }, [sessionId, onProviderChange]);

  async function handleConnect(provider: string) {
    if (!sessionId) return;
    window.location.href = getCalendarAuthUrl(provider, sessionId);
  }

  async function handleDisconnect(provider: string) {
    if (!sessionId) return;
    setLoading(provider);
    try {
      await disconnectCalendar(provider, sessionId);
      onProviderChange(connectedProviders.filter((p) => p !== provider));
      onDismissReconnect(provider);
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Calendars</p>

      {PROVIDERS.map((p) => {
        const connected = connectedProviders.includes(p.id);
        const reconnectNeeded = needsReconnect.includes(p.id);
        const busy = loading === p.id;

        return (
          <div key={p.id} className="flex flex-col gap-2">
            <div
              className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 shadow-sm transition-all ${
                reconnectNeeded
                  ? "border-amber-300 bg-amber-50 ring-1 ring-amber-200"
                  : "border-gray-200 bg-white"
              }`}
            >
              {/* Icon */}
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${p.iconBg}`}>
                <span className={`text-sm font-bold ${p.iconColor}`}>{p.iconText}</span>
              </div>

              {/* Label */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{p.label}</p>
                <p className={`text-xs ${reconnectNeeded ? "text-amber-600 font-medium" : connected ? "text-green-600" : "text-gray-400"}`}>
                  {reconnectNeeded ? "⚠ Token expired" : connected ? "Connected" : "Not connected"}
                </p>
              </div>

              {/* Action */}
              {connected && !reconnectNeeded ? (
                <button
                  onClick={() => handleDisconnect(p.id)}
                  disabled={busy}
                  title="Disconnect"
                  className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors disabled:opacity-50"
                >
                  {busy ? <Spinner /> : <Unlink size={16} />}
                </button>
              ) : (
                <button
                  onClick={() => handleConnect(p.id)}
                  disabled={busy}
                  title={reconnectNeeded ? "Reconnect" : "Connect"}
                  className={`rounded-lg p-1.5 transition-colors disabled:opacity-50 ${
                    reconnectNeeded
                      ? "text-amber-600 hover:bg-amber-100"
                      : "text-gray-400 hover:bg-green-50 hover:text-green-600"
                  }`}
                >
                  {busy ? <Spinner /> : reconnectNeeded ? <AlertTriangle size={16} /> : <Link2 size={16} />}
                </button>
              )}
            </div>

            {/* Inline reconnect banner */}
            {reconnectNeeded && (
              <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
                <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-600" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-amber-800">Reconnect needed</p>
                  <p className="text-xs text-amber-700 mt-0.5">
                    Your {p.label} token expired mid-conversation.
                  </p>
                  <button
                    onClick={() => handleConnect(p.id)}
                    className="mt-1.5 rounded-md bg-amber-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-amber-700 transition-colors"
                  >
                    Reconnect now
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {connectedProviders.length > 0 && needsReconnect.length === 0 && (
        <div className="flex items-center gap-1.5 text-xs text-green-600">
          <CheckCircle size={12} />
          <span>Ready to schedule</span>
        </div>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <span className="h-4 w-4 block rounded-full border-2 border-gray-300 border-t-gray-600 animate-spin" />
  );
}
