"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { sendMessage } from "@/lib/api";
import type { Message } from "@/lib/types";

const SESSION_KEY = "ai_calendar_session_id";

export function useChat() {
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connectedProviders, setConnectedProviders] = useState<string[]>([]);
  const initialised = useRef(false);

  // Initialise session ID (persist across page reloads)
  useEffect(() => {
    if (initialised.current) return;
    initialised.current = true;

    const existing = localStorage.getItem(SESSION_KEY);
    const id = existing ?? uuidv4();
    if (!existing) localStorage.setItem(SESSION_KEY, id);
    setSessionId(id);

    // Warm up the conversation with a greeting
    const greeting: Message = {
      id: uuidv4(),
      role: "assistant",
      content:
        "Hello! I'm your AI scheduling assistant. I can help you book appointments on your Google Calendar or Outlook. What would you like to schedule today?",
      timestamp: new Date(),
    };
    setMessages([greeting]);
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || !sessionId) return;

      const userMsg: Message = {
        id: uuidv4(),
        role: "user",
        content: text.trim(),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setError(null);

      try {
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const data = await sendMessage(sessionId, text.trim(), timezone);

        const assistantMsg: Message = {
          id: uuidv4(),
          role: "assistant",
          content: data.response,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setConnectedProviders(data.connected_providers);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Something went wrong.";
        setError(msg);
        const errorMsg: Message = {
          id: uuidv4(),
          role: "assistant",
          content: `Sorry, I ran into an error: ${msg}. Please try again.`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId]
  );

  const refreshProviders = useCallback((providers: string[]) => {
    setConnectedProviders(providers);
  }, []);

  return {
    sessionId,
    messages,
    isLoading,
    error,
    connectedProviders,
    send,
    refreshProviders,
  };
}
