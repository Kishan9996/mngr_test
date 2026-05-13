"use client";

import { AuthScreen } from "@/components/AuthScreen";
import { ChatInterface } from "@/components/ChatInterface";
import { useAuth } from "@/hooks/useAuth";

export default function Home() {
  const { user, isLoading, login, register, logout } = useAuth();

  // Show nothing while hydrating from localStorage (avoids flicker)
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <span className="h-8 w-8 rounded-full border-4 border-brand-200 border-t-brand-600 animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <AuthScreen onLogin={login} onRegister={register} />;
  }

  return <ChatInterface user={user} onLogout={logout} />;
}
