"use client";

import { useCallback, useEffect, useState } from "react";
import { apiLogin, apiRegister } from "@/lib/api";
import {
  clearToken,
  getStoredUser,
  getToken,
  setStoredUser,
  setToken,
  type StoredUser,
} from "@/lib/auth";

export function useAuth() {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [isLoading, setIsLoading] = useState(true); // true while hydrating from localStorage

  // Hydrate from localStorage on mount
  useEffect(() => {
    const token = getToken();
    const stored = getStoredUser();
    if (token && stored) {
      setUser(stored);
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiLogin(email, password);
    setToken(data.token);
    const stored: StoredUser = { user_id: data.user_id, email: data.email };
    setStoredUser(stored);
    setUser(stored);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const data = await apiRegister(email, password);
    setToken(data.token);
    const stored: StoredUser = { user_id: data.user_id, email: data.email };
    setStoredUser(stored);
    setUser(stored);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return { user, isLoading, login, register, logout };
}
