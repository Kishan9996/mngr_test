"use client";

import { useEffect, useState } from "react";
import { Check, ChevronDown, ChevronUp, Loader2, Settings } from "lucide-react";
import { getProfile, updateProfile } from "@/lib/api";
import type { UserProfile } from "@/lib/types";

const DURATION_OPTIONS = [15, 30, 45, 60, 90, 120];

export function ProfilePanel() {
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [draft, setDraft] = useState<UserProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || profile) return;
    getProfile()
      .then((p) => { setProfile(p); setDraft(p); })
      .catch(() => setError("Failed to load preferences."));
  }, [open]);

  async function handleSave() {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateProfile(draft);
      setProfile(updated);
      setDraft(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const dirty = draft && profile && JSON.stringify(draft) !== JSON.stringify(profile);

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      {/* Header / toggle */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Settings size={14} className="text-gray-400" />
          <span className="text-xs font-semibold text-gray-600">Schedule preferences</span>
        </div>
        {open ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
      </button>

      {open && (
        <div className="border-t border-gray-100 px-4 py-4 space-y-4">
          {!draft ? (
            <div className="flex justify-center py-2">
              <Loader2 size={16} className="animate-spin text-gray-400" />
            </div>
          ) : (
            <>
              {/* Working hours */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-2">Working hours</label>
                <div className="flex items-center gap-2">
                  <TimeInput
                    value={draft.work_start}
                    onChange={(v) => setDraft({ ...draft, work_start: v })}
                  />
                  <span className="text-xs text-gray-400">to</span>
                  <TimeInput
                    value={draft.work_end}
                    onChange={(v) => setDraft({ ...draft, work_end: v })}
                  />
                </div>
              </div>

              {/* Default duration */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-2">Default meeting length</label>
                <div className="flex flex-wrap gap-1.5">
                  {DURATION_OPTIONS.map((d) => (
                    <button
                      key={d}
                      onClick={() => setDraft({ ...draft, default_duration_minutes: d })}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                        draft.default_duration_minutes === d
                          ? "bg-brand-600 text-white"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {d < 60 ? `${d}m` : `${d / 60}h`}
                    </button>
                  ))}
                </div>
              </div>

              {/* Timezone */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Timezone</label>
                <input
                  type="text"
                  value={draft.timezone}
                  onChange={(e) => setDraft({ ...draft, timezone: e.target.value })}
                  placeholder="e.g. Europe/London"
                  className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-700 outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-100 transition-all"
                />
              </div>

              {error && (
                <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
              )}

              <button
                onClick={handleSave}
                disabled={!dirty || saving}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-brand-600 py-2 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : saved ? (
                  <Check size={12} />
                ) : null}
                {saved ? "Saved!" : saving ? "Saving…" : "Save preferences"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function TimeInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="time"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="flex-1 rounded-lg border border-gray-200 px-2 py-1.5 text-xs text-gray-700 outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-100 transition-all"
    />
  );
}
