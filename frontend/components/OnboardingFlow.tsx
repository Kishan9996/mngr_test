"use client";

import React, { useEffect, useState } from "react";
import {
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  Link2,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import { getCalendarAuthUrl, getCalendarStatus, updateProfile } from "@/lib/api";
import { getStoredSessionId } from "@/lib/auth";
import type { StoredUser } from "@/lib/auth";

// ── Types ─────────────────────────────────────────────────────────────────────

type Step = "welcome" | "preferences" | "calendar";

const STEP_ORDER: Step[] = ["welcome", "preferences", "calendar"];
const DURATION_OPTIONS = [15, 30, 45, 60, 90];

const PROVIDERS = [
  {
    id: "google",
    label: "Google Calendar",
    bg: "bg-red-50",
    border: "border-red-200",
    icon: "G",
    iconColor: "text-red-600",
  },
  {
    id: "outlook",
    label: "Outlook Calendar",
    bg: "bg-blue-50",
    border: "border-blue-200",
    icon: "O",
    iconColor: "text-blue-700",
  },
];

// ── Main ──────────────────────────────────────────────────────────────────────

interface OnboardingProps {
  user: StoredUser;
  onComplete: () => void;
}

export function OnboardingFlow({ user, onComplete }: OnboardingProps) {
  const [step, setStep] = useState<Step>("welcome");
  const [workStart, setWorkStart] = useState("09:00");
  const [workEnd, setWorkEnd] = useState("17:00");
  const [duration, setDuration] = useState(30);
  const [timezone, setTimezone] = useState("UTC");
  const [connectedProviders, setConnectedProviders] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
  }, []);

  // Poll calendar status and detect OAuth return on the calendar step
  useEffect(() => {
    if (step !== "calendar") return;
    const sessionId = getStoredSessionId();
    if (!sessionId) return;

    // Check if we returned from an OAuth redirect
    const params = new URLSearchParams(window.location.search);
    const justConnected = params.get("calendar_connected");
    if (justConnected) {
      setConnectedProviders((prev) =>
        prev.includes(justConnected) ? prev : [...prev, justConnected]
      );
      window.history.replaceState({}, "", window.location.pathname);
    }

    const poll = setInterval(async () => {
      try {
        const status = await getCalendarStatus(sessionId);
        setConnectedProviders(status.connected_providers);
      } catch {
        // ignore polling errors
      }
    }, 2000);

    return () => clearInterval(poll);
  }, [step]);

  const stepIndex = STEP_ORDER.indexOf(step);

  async function savePreferences() {
    setSaving(true);
    try {
      await updateProfile({
        work_start: workStart,
        work_end: workEnd,
        default_duration_minutes: duration,
        timezone,
      });
      setStep("calendar");
    } finally {
      setSaving(false);
    }
  }

  async function finish() {
    setSaving(true);
    try {
      await updateProfile({ onboarding_completed: true });
      onComplete();
    } finally {
      setSaving(false);
    }
  }

  function connectCalendar(provider: string) {
    const sessionId = getStoredSessionId();
    if (sessionId) {
      window.location.href = getCalendarAuthUrl(provider, sessionId);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 to-blue-50 px-4">
      <div className="w-full max-w-lg">

        {/* Step dots */}
        <div className="mb-8 flex items-center justify-center gap-2">
          {STEP_ORDER.map((s, i) => {
            const active = i <= stepIndex;
            const connector = i < STEP_ORDER.length - 1;
            const past = i < stepIndex;
            return (
              <React.Fragment key={s}>
                <div
                  className={
                    "h-2.5 w-2.5 rounded-full transition-all " +
                    (active ? "bg-brand-600 scale-110" : "bg-gray-200")
                  }
                />
                {connector && (
                  <div
                    className={
                      "h-px w-10 transition-all " +
                      (past ? "bg-brand-300" : "bg-gray-200")
                    }
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Card */}
        <div className="rounded-3xl bg-white shadow-xl px-8 py-10">
          {step === "welcome" && (
            <WelcomeStep user={user} onNext={() => setStep("preferences")} />
          )}
          {step === "preferences" && (
            <PreferencesStep
              workStart={workStart}
              setWorkStart={setWorkStart}
              workEnd={workEnd}
              setWorkEnd={setWorkEnd}
              duration={duration}
              setDuration={setDuration}
              timezone={timezone}
              setTimezone={setTimezone}
              saving={saving}
              onNext={savePreferences}
            />
          )}
          {step === "calendar" && (
            <CalendarStep
              connectedProviders={connectedProviders}
              saving={saving}
              onConnect={connectCalendar}
              onFinish={finish}
            />
          )}
        </div>

        <p className="mt-4 text-center text-xs text-gray-400">
          Step {stepIndex + 1} of {STEP_ORDER.length}
        </p>
      </div>
    </div>
  );
}

// ── Step 1 — Welcome ──────────────────────────────────────────────────────────

interface WelcomeStepProps {
  user: StoredUser;
  onNext: () => void;
}

function WelcomeStep({ user, onNext }: WelcomeStepProps) {
  return (
    <div className="flex flex-col items-center text-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-600 text-white shadow-lg">
        <Calendar size={32} />
      </div>

      <h1 className="text-2xl font-bold text-gray-900">
        Welcome, {user.email.split("@")[0]}!
      </h1>
      <p className="mt-2 text-sm text-gray-500">
        Your AI scheduling assistant is ready.
      </p>

      <div className="mt-8 w-full space-y-4 text-left">
        <FeatureRow
          icon={<MessageSquare size={16} />}
          title="Talk naturally"
          body="Say what you need — 'book a team standup this week' — and I'll handle the rest."
        />
        <FeatureRow
          icon={<Calendar size={16} />}
          title="Checks all your calendars"
          body="Slots are checked across every calendar in your Google or Outlook account."
        />
        <FeatureRow
          icon={<Clock size={16} />}
          title="Next 2-3 days by default"
          body="I suggest the nearest available window within your working hours."
        />
        <FeatureRow
          icon={<Sparkles size={16} />}
          title="Always confirms before booking"
          body="You review the slot and details before anything is created."
        />
      </div>

      <button
        onClick={onNext}
        className="mt-8 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-3 font-semibold text-white hover:bg-brand-700 transition-colors"
      >
        Get started
        <ArrowRight size={18} />
      </button>
    </div>
  );
}

// ── Step 2 — Preferences ──────────────────────────────────────────────────────

interface PreferencesStepProps {
  workStart: string;
  setWorkStart: (v: string) => void;
  workEnd: string;
  setWorkEnd: (v: string) => void;
  duration: number;
  setDuration: (v: number) => void;
  timezone: string;
  setTimezone: (v: string) => void;
  saving: boolean;
  onNext: () => void;
}

function PreferencesStep({
  workStart, setWorkStart,
  workEnd, setWorkEnd,
  duration, setDuration,
  timezone, setTimezone,
  saving, onNext,
}: PreferencesStepProps) {
  return (
    <div>
      <h2 className="text-xl font-bold text-gray-900">Your schedule</h2>
      <p className="mt-1 text-sm text-gray-500">
        I only suggest slots within your working hours. Change these any time from the sidebar.
      </p>

      <div className="mt-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Working hours
          </label>
          <div className="flex items-center gap-3">
            <input
              type="time"
              value={workStart}
              onChange={(e) => setWorkStart(e.target.value)}
              className="flex-1 rounded-xl border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 transition-all"
            />
            <span className="text-sm text-gray-400">to</span>
            <input
              type="time"
              value={workEnd}
              onChange={(e) => setWorkEnd(e.target.value)}
              className="flex-1 rounded-xl border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 transition-all"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Default meeting length
          </label>
          <div className="flex flex-wrap gap-2">
            {DURATION_OPTIONS.map((d) => (
              <button
                key={d}
                onClick={() => setDuration(d)}
                className={
                  "rounded-xl px-4 py-2 text-sm font-medium transition-colors " +
                  (duration === d
                    ? "bg-brand-600 text-white shadow-sm"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200")
                }
              >
                {d < 60 ? `${d} min` : `${d / 60} hr`}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Timezone
          </label>
          <input
            type="text"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            placeholder="e.g. Europe/London"
            className="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 transition-all"
          />
          <p className="mt-1 text-xs text-gray-400">Auto-detected from your browser</p>
        </div>
      </div>

      <button
        onClick={onNext}
        disabled={saving}
        className="mt-7 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-3 font-semibold text-white hover:bg-brand-700 disabled:opacity-60 transition-colors"
      >
        {saving ? "Saving…" : "Save & continue"}
        {!saving && <ArrowRight size={18} />}
      </button>
    </div>
  );
}

// ── Step 3 — Calendar connect ─────────────────────────────────────────────────

interface CalendarStepProps {
  connectedProviders: string[];
  saving: boolean;
  onConnect: (provider: string) => void;
  onFinish: () => void;
}

function CalendarStep({ connectedProviders, saving, onConnect, onFinish }: CalendarStepProps) {
  const anyConnected = connectedProviders.length > 0;

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-900">Connect your calendar</h2>
      <p className="mt-1 text-sm text-gray-500">
        Connect at least one calendar so I can check availability and book appointments.
      </p>

      <div className="mt-6 space-y-3">
        {PROVIDERS.map((p) => {
          const connected = connectedProviders.includes(p.id);
          return (
            <button
              key={p.id}
              onClick={() => { if (!connected) onConnect(p.id); }}
              disabled={connected}
              className={
                "flex w-full items-center gap-4 rounded-2xl border-2 px-5 py-4 text-left transition-all " +
                (connected
                  ? p.bg + " " + p.border + " cursor-default"
                  : "border-gray-200 bg-white hover:border-brand-300 hover:bg-brand-50")
              }
            >
              <div className={"flex h-10 w-10 shrink-0 items-center justify-center rounded-xl " + p.bg + " border " + p.border}>
                <span className={"text-base font-bold " + p.iconColor}>{p.icon}</span>
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-800">{p.label}</p>
                <p className={"text-xs " + (connected ? "text-green-600 font-medium" : "text-gray-400")}>
                  {connected ? "Connected" : "Click to connect via OAuth"}
                </p>
              </div>
              {connected
                ? <CheckCircle2 size={20} className="shrink-0 text-green-500" />
                : <Link2 size={18} className="shrink-0 text-gray-400" />
              }
            </button>
          );
        })}
      </div>

      {anyConnected && (
        <div className="mt-4 flex items-center gap-2 rounded-xl bg-green-50 border border-green-200 px-4 py-3">
          <CheckCircle2 size={16} className="text-green-500 shrink-0" />
          <p className="text-sm text-green-700 font-medium">
            Calendar connected — you&#39;re all set!
          </p>
        </div>
      )}

      <button
        onClick={onFinish}
        disabled={saving}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-3 font-semibold text-white hover:bg-brand-700 disabled:opacity-60 transition-colors"
      >
        {saving ? "Setting up…" : anyConnected ? "Start scheduling" : "Skip for now"}
        {!saving && <ArrowRight size={18} />}
      </button>

      {!anyConnected && (
        <p className="mt-2 text-center text-xs text-gray-400">
          You can connect a calendar later from the sidebar.
        </p>
      )}
    </div>
  );
}

// ── Feature row ───────────────────────────────────────────────────────────────

interface FeatureRowProps {
  icon: React.ReactElement;
  title: string;
  body: string;
}

function FeatureRow({ icon, title, body }: FeatureRowProps) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
        {icon}
      </div>
      <div>
        <p className="text-sm font-semibold text-gray-800">{title}</p>
        <p className="text-xs text-gray-500 mt-0.5">{body}</p>
      </div>
    </div>
  );
}
