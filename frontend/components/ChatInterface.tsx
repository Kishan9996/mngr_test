"use client";

import { useEffect, useRef, useState } from "react";
import { Calendar, CalendarDays, LogOut, MessageSquare, Send } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import type { StoredUser } from "@/lib/auth";
import { BookingsView } from "./BookingsView";
import { CalendarConnect } from "./CalendarConnect";
import { ChatMessage } from "./ChatMessage";
import { ProfilePanel } from "./ProfilePanel";
import { TypingIndicator } from "./TypingIndicator";

const QUICK_PROMPTS = [
  "Schedule a 30-min meeting tomorrow",
  "Book a 1-hour call this week",
  "Find a free slot on Friday",
];

type View = "chat" | "bookings";

interface Props {
  user: StoredUser;
  onLogout: () => void;
}

export function ChatInterface({ user, onLogout }: Props) {
  const {
    sessionId,
    messages,
    isLoading,
    connectedProviders,
    needsReconnect,
    send,
    refreshProviders,
    dismissReconnect,
  } = useChat();

  const [view, setView] = useState<View>("chat");
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (view === "chat") {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading, view]);

  function handleSend() {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    send(text);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* ── Main area ─────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0">

        {/* Header */}
        <header className="flex items-center gap-3 border-b border-gray-200 bg-white px-6 py-3 shadow-sm">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white shrink-0">
            <Calendar size={20} />
          </div>
          <span className="text-base font-semibold text-gray-900 hidden sm:block">
            AI Scheduling Assistant
          </span>

          {/* Tab switcher */}
          <div className="ml-4 flex rounded-xl bg-gray-100 p-1 gap-1">
            <TabButton
              active={view === "chat"}
              icon={<MessageSquare size={14} />}
              label="Chat"
              onClick={() => setView("chat")}
            />
            <TabButton
              active={view === "bookings"}
              icon={<CalendarDays size={14} />}
              label="Bookings"
              onClick={() => setView("bookings")}
              badge={connectedProviders.length > 0 ? undefined : undefined}
            />
          </div>

          <div className="flex-1" />
          <span className="text-xs text-gray-400 hidden sm:block">{user.email}</span>
          <button
            onClick={onLogout}
            title="Sign out"
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          >
            <LogOut size={16} />
          </button>
        </header>

        {/* ── Chat view ─────────────────────────────────────────────── */}
        {view === "chat" && (
          <>
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              {isLoading && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>

            {messages.length === 1 && !isLoading && (
              <div className="flex flex-wrap gap-2 px-6 pb-2">
                {QUICK_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => send(p)}
                    className="rounded-full border border-brand-500 bg-brand-50 px-3 py-1.5 text-xs text-brand-700 hover:bg-brand-100 transition-colors"
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}

            <div className="border-t border-gray-200 bg-white px-6 py-4">
              <div className="flex items-end gap-3 rounded-2xl border border-gray-300 bg-gray-50 px-4 py-3 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-100 transition-all">
                <textarea
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type a message… (Enter to send)"
                  className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none max-h-32"
                  disabled={isLoading}
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <Send size={15} />
                </button>
              </div>
              <p className="mt-1.5 text-center text-[11px] text-gray-400">
                Verify appointment details before relying on them.
              </p>
            </div>
          </>
        )}

        {/* ── Bookings view ──────────────────────────────────────────── */}
        {view === "bookings" && (
          <BookingsView
            sessionId={sessionId}
            connectedProviders={connectedProviders}
          />
        )}
      </div>

      {/* ── Sidebar ───────────────────────────────────────────────────── */}
      <aside className="w-72 shrink-0 border-l border-gray-200 bg-white flex flex-col gap-6 px-5 py-6 overflow-y-auto">
        <CalendarConnect
          sessionId={sessionId}
          connectedProviders={connectedProviders}
          needsReconnect={needsReconnect}
          onProviderChange={refreshProviders}
          onDismissReconnect={dismissReconnect}
        />

        <ProfilePanel />

        <div className="rounded-xl bg-brand-50 border border-brand-100 p-4">
          <p className="text-xs font-semibold text-brand-700 mb-2">Tips</p>
          <ul className="space-y-1.5 text-xs text-brand-600 list-disc list-inside">
            <li>Connect a calendar to get started</li>
            <li>Switch to Bookings to see all events</li>
            <li>Set your working hours in preferences</li>
            <li>Confirm before I book anything</li>
          </ul>
        </div>

        {process.env.NODE_ENV === "development" && sessionId && (
          <div className="rounded-lg bg-gray-100 p-3">
            <p className="text-[10px] font-mono text-gray-500 break-all">Session: {sessionId}</p>
          </div>
        )}
      </aside>
    </div>
  );
}

function TabButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
        active
          ? "bg-white text-gray-900 shadow-sm"
          : "text-gray-500 hover:text-gray-700"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
