"use client";

import { useState } from "react";
import { AlertCircle, Calendar, CheckCircle2, Loader2 } from "lucide-react";

interface Props {
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string) => Promise<void>;
}

type Mode = "login" | "register";

export function AuthScreen({ onLogin, onRegister }: Props) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const passwordOk = password.length === 0 || password.length >= 8;
  const showPasswordHint = mode === "register" && password.length > 0 && password.length < 8;

  function handleEmailChange(e: React.ChangeEvent<HTMLInputElement>) {
    setEmail(e.target.value);
    if (error) setError(null);
  }

  function handlePasswordChange(e: React.ChangeEvent<HTMLInputElement>) {
    setPassword(e.target.value);
    if (error) setError(null);
  }

  function switchMode(m: Mode) {
    setMode(m);
    setError(null);
    // Don't clear email/password — UX convenience when switching between tabs
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    // Client-side guard before hitting the network
    if (mode === "register" && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setError(null);
    setLoading(true);
    try {
      if (mode === "login") {
        await onLogin(email.trim().toLowerCase(), password);
      } else {
        await onRegister(email.trim().toLowerCase(), password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 to-blue-100 px-4">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-lg">
            <Calendar size={28} />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900">AI Scheduling Assistant</h1>
            <p className="mt-1 text-sm text-gray-500">Book appointments with natural language</p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-2xl bg-white px-8 py-8 shadow-xl">

          {/* Mode switcher */}
          <div className="mb-6 flex rounded-xl bg-gray-100 p-1">
            {(["login", "register"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                className={
                  "flex-1 rounded-lg py-2 text-sm font-medium transition-all " +
                  (mode === m
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-700")
                }
              >
                {m === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>

            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={handleEmailChange}
                placeholder="you@example.com"
                disabled={loading}
                className="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 disabled:bg-gray-50 disabled:text-gray-400 transition-all"
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                required
                value={password}
                onChange={handlePasswordChange}
                placeholder={mode === "register" ? "At least 8 characters" : "••••••••"}
                disabled={loading}
                className={
                  "w-full rounded-xl border px-4 py-2.5 text-sm outline-none disabled:bg-gray-50 disabled:text-gray-400 transition-all " +
                  (showPasswordHint
                    ? "border-amber-300 focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                    : "border-gray-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-100")
                }
              />
              {/* Password strength hint for register */}
              {mode === "register" && password.length > 0 && (
                <div className={
                  "mt-1.5 flex items-center gap-1.5 text-xs " +
                  (passwordOk ? "text-green-600" : "text-amber-600")
                }>
                  {passwordOk
                    ? <CheckCircle2 size={12} />
                    : <AlertCircle size={12} />}
                  {passwordOk
                    ? "Looks good"
                    : `${8 - password.length} more character${8 - password.length === 1 ? "" : "s"} needed`}
                </div>
              )}
            </div>

            {/* Error banner */}
            {error && (
              <div className="flex items-start gap-2.5 rounded-xl bg-red-50 border border-red-200 px-4 py-3">
                <AlertCircle size={15} className="shrink-0 mt-0.5 text-red-500" />
                <p className="text-sm text-red-700 leading-snug">{error}</p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {loading && <Loader2 size={15} className="animate-spin" />}
              {loading
                ? mode === "login" ? "Signing in…" : "Creating account…"
                : mode === "login" ? "Sign in" : "Create account"}
            </button>

          </form>

          <p className="mt-6 text-center text-xs text-gray-400">
            Your calendar tokens are stored securely and tied to your account.
          </p>
        </div>
      </div>
    </div>
  );
}
