"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { clearChatHistory, getCalendarStatus, getChatHistory, sendMessage } from "@/lib/api";
import { getStoredSessionId } from "@/lib/auth";
import type { Message } from "@/lib/types";

const GREETING: Message = {
  id: "greeting",
  role: "assistant",
  content:
    "Hello! I'm your AI scheduling assistant.\n\nWhat would you like to schedule? Tell me the purpose of the meeting and I'll find available slots across your calendar — usually within the next 2-3 days.",
  timestamp: new Date(),
};

export function useChat() {
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectedProviders, setConnectedProviders] = useState<string[]>([]);
  const [needsReconnect, setNeedsReconnect] = useState<string[]>([]);
  const initialised = useRef(false);

  useEffect(() => {
    if (initialised.current) return;
    initialised.current = true;

    // Session ID is always server-provided (set during login/register via useAuth).
    // Never generate a client-side UUID — that would bypass the isolation guarantee.
    const id = getStoredSessionId();
    if (!id) {
      // Auth guard should prevent reaching here without a session_id
      setHistoryLoading(false);
      setMessages([GREETING]);
      return;
    }
    setSessionId(id);

    // Fetch history and initial calendar status in parallel
    setHistoryLoading(true);
    Promise.all([
      getChatHistory(id),
      getCalendarStatus(id).catch(() => ({ connected_providers: [] as string[] })),
    ]).then(([{ messages: serverMsgs }, calStatus]) => {
      setMessages(
        serverMsgs.length > 0
          ? serverMsgs.map((m) => ({
              id: uuidv4(),
              role: m.role as "user" | "assistant",
              content: m.content,
              timestamp: new Date(),
            }))
          : [GREETING]
      );
      setConnectedProviders(calStatus.connected_providers);
    })
    .catch(() => setMessages([GREETING]))
    .finally(() => setHistoryLoading(false));
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || !sessionId) return;

      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), role: "user", content: text.trim(), timestamp: new Date() },
      ]);
      setIsLoading(true);
      setError(null);

      try {
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const data = await sendMessage(sessionId, text.trim(), timezone);

        setMessages((prev) => [
          ...prev,
          { id: uuidv4(), role: "assistant", content: data.response, timestamp: new Date() },
        ]);
        setConnectedProviders(data.connected_providers);
        if (data.needs_reconnect_providers.length > 0) {
          setNeedsReconnect(data.needs_reconnect_providers);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Something went wrong.";
        setError(msg);
        setMessages((prev) => [
          ...prev,
          { id: uuidv4(), role: "assistant", content: `Sorry — ${msg}`, timestamp: new Date() },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId]
  );

  const refreshProviders = useCallback((providers: string[]) => {
    setConnectedProviders(providers);
    setNeedsReconnect((prev) => prev.filter((p) => !providers.includes(p)));
  }, []);

  const dismissReconnect = useCallback((provider: string) => {
    setNeedsReconnect((prev) => prev.filter((p) => p !== provider));
  }, []);

  const resetConversation = useCallback(async () => {
    if (!sessionId) return;
    try {
      await clearChatHistory(sessionId);
    } catch { /* ignore */ }
    setMessages([GREETING]);
    setNeedsReconnect([]);
    setError(null);
  }, [sessionId]);

  return {
    sessionId,
    messages,
    isLoading,
    historyLoading,
    error,
    connectedProviders,
    needsReconnect,
    send,
    refreshProviders,
    dismissReconnect,
    resetConversation,
  };
}
