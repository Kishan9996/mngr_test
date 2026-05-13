import { CheckCircle2 } from "lucide-react";
import type { Message } from "@/lib/types";

interface Props {
  message: Message;
  onOptionSelect?: (text: string) => void;
}

// ── Slot detection ────────────────────────────────────────────────────────────

interface SlotOption {
  index: number;
  full: string;   // full label from the message
  short: string;  // truncated for the button
}

const TIME_RE = /\d{1,2}:\d{2}|\bAM\b|\bPM\b/i;

function parseSlotOptions(content: string): SlotOption[] {
  const options: SlotOption[] = [];
  for (const line of content.split("\n")) {
    // Match "1. text" or "1) text", optionally with ** bold markers
    const m = line.match(/^\s*(\d+)[.)]\s+\*{0,2}(.+?)\*{0,2}\s*$/);
    if (!m) continue;
    const label = m[2].replace(/\*\*/g, "").trim();
    // Must look like a time slot (contain a time pattern) and be substantial
    if (TIME_RE.test(label) && label.length > 8) {
      options.push({
        index: parseInt(m[1], 10),
        full: label,
        short: label.length > 38 ? label.slice(0, 36) + "…" : label,
      });
    }
  }
  // Only surface buttons when there are 2+ slots — avoids false positives on
  // single-item confirmations
  return options.length >= 2 ? options : [];
}

// ── Booking success detection ─────────────────────────────────────────────────

function isBookingSuccess(content: string): boolean {
  return (
    /your appointment is booked/i.test(content) ||
    /your (meeting|event|appointment) (is|has been) (booked|confirmed|scheduled|created)/i.test(content) ||
    /successfully booked/i.test(content)
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ChatMessage({ message, onOptionSelect }: Props) {
  const isUser = message.role === "user";
  const success = !isUser && isBookingSuccess(message.content);
  const slots = !isUser ? parseSlotOptions(message.content) : [];
  const showButtons = slots.length > 0 && !!onOptionSelect;

  return (
    <div className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
          isUser ? "bg-gray-200 text-gray-700" : success ? "bg-green-500 text-white" : "bg-brand-600 text-white"
        }`}
      >
        {isUser ? "You" : success ? <CheckCircle2 size={15} /> : "AI"}
      </div>

      <div className={`flex flex-col gap-2 max-w-[78%] ${isUser ? "items-end" : "items-start"}`}>
        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
            isUser
              ? "rounded-tr-sm bg-brand-600 text-white"
              : success
              ? "rounded-tl-sm bg-green-50 border border-green-200 text-gray-800"
              : "rounded-tl-sm bg-white border border-gray-200 text-gray-800"
          }`}
        >
          {/* Booking success badge */}
          {success && (
            <div className="flex items-center gap-1.5 mb-2 text-green-700 font-semibold text-xs">
              <CheckCircle2 size={13} />
              Appointment booked
            </div>
          )}

          <FormattedMessage content={message.content} isUser={isUser} />

          <p
            className={`mt-1 text-[11px] ${
              isUser ? "text-blue-200 text-right" : success ? "text-green-400" : "text-gray-400"
            }`}
          >
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>

        {/* Clickable slot buttons */}
        {showButtons && (
          <div className="flex flex-wrap gap-2">
            {slots.map((slot) => (
              <button
                key={slot.index}
                onClick={() => onOptionSelect!(`Option ${slot.index}`)}
                className="flex items-center gap-2 rounded-xl border border-brand-300 bg-brand-50 px-3 py-2 text-left text-xs text-brand-700 hover:bg-brand-100 hover:border-brand-400 active:scale-95 transition-all shadow-sm"
                title={slot.full}
              >
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white text-[10px] font-bold">
                  {slot.index}
                </span>
                {slot.short}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Markdown-lite renderer ────────────────────────────────────────────────────

function FormattedMessage({ content, isUser }: { content: string; isUser: boolean }) {
  const lines = content.split("\n");

  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        if (!line.trim()) return <br key={i} />;

        const parts = line.split(/(\*\*[^*]+\*\*)/g);
        const rendered = parts.map((part, j) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={j} className="font-semibold">
              {part.slice(2, -2)}
            </strong>
          ) : (
            <span key={j}>{part}</span>
          )
        );

        if (/^\d+[.)]/.test(line.trim())) {
          return <p key={i} className="pl-1">{rendered}</p>;
        }
        return <p key={i}>{rendered}</p>;
      })}
    </div>
  );
}
