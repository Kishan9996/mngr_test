"use client";
import { useState, useCallback } from "react";
import { v4 as uuid } from "uuid";
import { api } from "@/lib/api";
import { Message } from "@/lib/types";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (text: string) => {
    const userMsg: Message = { id: uuid(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError(null);
    try {
      const { reply, session_id } = await api.sendMessage(text, sessionId);
      if (!sessionId) setSessionId(session_id);
      const assistantMsg: Message = { id: uuid(), role: "assistant", content: reply };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const clearChat = () => {
    setMessages([]);
    setSessionId(undefined);
    setError(null);
  };

  return { messages, loading, error, sendMessage, clearChat };
}
