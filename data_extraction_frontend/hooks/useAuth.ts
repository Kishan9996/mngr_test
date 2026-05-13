"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { UserInfo } from "@/lib/types";

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.me()
      .then((u) => setUser(u as UserInfo))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const u = await api.login(email, password);
    setUser(u as UserInfo);
  };

  const register = async (email: string, password: string, orgName: string) => {
    const u = await api.register(email, password, orgName);
    setUser(u as UserInfo);
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
  };

  return { user, loading, login, register, logout };
}
