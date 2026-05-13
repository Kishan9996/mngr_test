"use client";
import { useAuth } from "@/hooks/useAuth";
import { useChat } from "@/hooks/useChat";
import AuthScreen from "@/components/AuthScreen";
import ChatInterface from "@/components/ChatInterface";

export default function Home() {
  const { user, loading: authLoading, login, register, logout } = useAuth();
  const { messages, loading: chatLoading, error, sendMessage, clearChat } = useChat();

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <AuthScreen onLogin={login} onRegister={register} />;
  }

  return (
    <ChatInterface
      user={user}
      messages={messages}
      loading={chatLoading}
      error={error}
      onSend={sendMessage}
      onClear={clearChat}
      onLogout={logout}
    />
  );
}
