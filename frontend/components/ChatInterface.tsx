"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Calendar } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { CalendarConnect } from "./CalendarConnect";
import { ChatMessage } from "./ChatMessage";
import { TypingIndicator } from "./TypingIndicator";

const QUICK_PROMPTS = [
  "Schedule a 30-min meeting tomorrow",
  "Book a 1-hour call this week",
  "Find a free slot on Friday",
];

export function ChatInterface() {
  const {
    sessionId,
    messages,
    isLoading,
    connectedProviders,
    send,
    refreshProviders,
  } = useChat();

  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to the latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

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
      {/* ── Main chat area ────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center gap-3 border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Calendar size={20} />
          </div>
          <div>
            <h1 className="text-base font-semibold text-gray-900">
              AI Scheduling Assistant
            </h1>
            <p className="text-xs text-gray-500">
              Powered by Claude · Book appointments in seconds
            </p>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
          {isLoading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>

        {/* Quick prompts (only shown when chat is empty beyond greeting) */}
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

        {/* Input area */}
        <div className="border-t border-gray-200 bg-white px-6 py-4">
          <div className="flex items-end gap-3 rounded-2xl border border-gray-300 bg-gray-50 px-4 py-3 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-100 transition-all">
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message… (Enter to send, Shift+Enter for new line)"
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
            AI can make mistakes — always verify your appointment details.
          </p>
        </div>
      </div>

      {/* ── Sidebar ───────────────────────────────────────────────────── */}
      <aside className="w-72 shrink-0 border-l border-gray-200 bg-white flex flex-col gap-6 px-5 py-6 overflow-y-auto">
        <CalendarConnect
          sessionId={sessionId}
          connectedProviders={connectedProviders}
          onProviderChange={refreshProviders}
        />

        {/* Tips */}
        <div className="rounded-xl bg-brand-50 border border-brand-100 p-4">
          <p className="text-xs font-semibold text-brand-700 mb-2">Tips</p>
          <ul className="space-y-1.5 text-xs text-brand-600 list-disc list-inside">
            <li>Connect a calendar to get started</li>
            <li>Tell me the meeting purpose and duration</li>
            <li>I'll show available slots within 2–3 days</li>
            <li>Confirm before I book anything</li>
          </ul>
        </div>

        {/* Session info (dev aid) */}
        {process.env.NODE_ENV === "development" && sessionId && (
          <div className="rounded-lg bg-gray-100 p-3">
            <p className="text-[10px] font-mono text-gray-500 break-all">
              Session: {sessionId}
            </p>
          </div>
        )}
      </aside>
    </div>
  );
}
