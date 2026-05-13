"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { AuthScreen } from "@/components/AuthScreen";
import { ChatInterface } from "@/components/ChatInterface";
import { OnboardingFlow } from "@/components/OnboardingFlow";
import { useAuth } from "@/hooks/useAuth";
import { getProfile } from "@/lib/api";
import type { UserProfile } from "@/lib/types";

type AppState = "loading" | "auth" | "onboarding" | "app";

export default function Home() {
  const { user, isLoading: authLoading, login, register, logout } = useAuth();
  const [appState, setAppState] = useState<AppState>("loading");
  const [profile, setProfile] = useState<UserProfile | null>(null);

  // Once auth is resolved, check whether onboarding is needed
  useEffect(() => {
    if (authLoading) return;

    if (!user) {
      setAppState("auth");
      return;
    }

    // Fetch profile to check onboarding status
    getProfile()
      .then((p) => {
        setProfile(p);
        setAppState(p.onboarding_completed ? "app" : "onboarding");
      })
      .catch(() => {
        // If profile fetch fails, skip onboarding and go to app
        setAppState("app");
      });
  }, [authLoading, user]);

  // ── Loading spinner ────────────────────────────────────────────────────────
  if (appState === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <Loader2 size={24} className="animate-spin text-brand-600" />
          <p className="text-sm text-gray-400">Loading…</p>
        </div>
      </div>
    );
  }

  // ── Auth screen ────────────────────────────────────────────────────────────
  if (appState === "auth" || !user) {
    return <AuthScreen onLogin={login} onRegister={register} />;
  }

  // ── Onboarding ─────────────────────────────────────────────────────────────
  if (appState === "onboarding") {
    return (
      <OnboardingFlow
        user={user}
        onComplete={() => setAppState("app")}
      />
    );
  }

  // ── Main app ───────────────────────────────────────────────────────────────
  return <ChatInterface user={user} onLogout={logout} />;
}
