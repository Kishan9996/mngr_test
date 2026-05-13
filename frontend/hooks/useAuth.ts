"use client";

import { useCallback, useEffect, useState } from "react";
import { apiLogin, apiLogout, apiMe, apiRegister } from "@/lib/api";
import {
  clearSession,
  getStoredSessionId,
  getStoredUser,
  SESSION_KEY,
  setStoredSessionId,
  setStoredUser,
  type StoredUser,
} from "@/lib/auth";

export function useAuth() {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Fast path: restore display info from localStorage immediately
    const cached = getStoredUser();
    if (cached) setUser(cached);

    // Verify the httpOnly cookie is still valid and sync the session_id
    apiMe()
      .then((me) => {
        if (me) {
          const stored: StoredUser = { user_id: me.user_id, email: me.email };
          setUser(stored);
          setStoredUser(stored);
          // Always use the server-provided session_id
          setStoredSessionId(me.session_id);
        } else {
          clearSession();
          setUser(null);
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiLogin(email, password);
    const stored: StoredUser = { user_id: data.user_id, email: data.email };
    setStoredUser(stored);
    // Server owns the session_id — always use what the server returns
    setStoredSessionId(data.session_id);
    setUser(stored);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const data = await apiRegister(email, password);
    const stored: StoredUser = { user_id: data.user_id, email: data.email };
    setStoredUser(stored);
    setStoredSessionId(data.session_id);
    setUser(stored);
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    // Wipe session so the next user cannot inherit this session_id
    clearSession();
    setUser(null);
  }, []);

  return { user, isLoading, login, register, logout };
}
