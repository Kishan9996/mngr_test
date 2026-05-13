"""Claude AI service with tool-use for calendar scheduling.

Design patterns:
- Strategy: implements AIService — swap LLM without touching callers.
- Command dispatch table: tool calls routed through _dispatch(), keeping
  the agentic loop free of conditionals.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.core.config import get_settings
from app.core.exceptions import AIServiceError, AppError, CalendarAuthError
from app.models.chat import ProcessResult
from app.services.ai.base import AIService
from app.services.profile.profile_service import ProfileService
from app.services.scheduling.scheduler import SchedulingService
from app.services.session.abstract_store import AbstractSessionStore

logger = logging.getLogger(__name__)

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_connected_calendars",
        "description": (
            "Return which calendar providers (google, outlook) the user has "
            "already connected. Call this at the start of every session to know "
            "which provider to use for availability and booking."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_available_slots",
        "description": (
            "Retrieve available time slots from the user's calendar for a given "
            "date range and appointment duration. Returns up to 6 open slots."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD (inclusive)."},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD (inclusive)."},
                "duration_minutes": {"type": "integer", "description": "Duration in minutes."},
                "calendar_provider": {"type": "string", "enum": ["google", "outlook"]},
                "timezone": {"type": "string", "description": "IANA timezone, e.g. 'Europe/London'."},
                "work_start": {"type": "string", "description": "Working hours start HH:MM. Default '09:00'."},
                "work_end": {"type": "string", "description": "Working hours end HH:MM. Default '17:00'."},
            },
            "required": ["date_from", "date_to", "duration_minutes", "calendar_provider"],
        },
    },
    {
        "name": "create_appointment",
        "description": (
            "Book an appointment on the user's calendar. Only call after the user "
            "has explicitly confirmed the time slot and title."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_datetime": {"type": "string", "description": "ISO 8601 with timezone offset."},
                "end_datetime": {"type": "string", "description": "ISO 8601 with timezone offset."},
                "timezone": {"type": "string"},
                "calendar_provider": {"type": "string", "enum": ["google", "outlook"]},
                "description": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "start_datetime", "end_datetime", "timezone", "calendar_provider"],
        },
    },
]

def _build_system_prompt() -> str:
    from datetime import date
    today = date.today().strftime("%A, %d %B %Y")
    return f"""You are a friendly and efficient AI scheduling assistant. \
Your sole purpose is to help users book appointments on their calendar.

Today's date is **{today}**. Never suggest or attempt to book appointments \
on a date or time that has already passed.

## Workflow
1. **Greet** the user and ask what they'd like to schedule.
2. **Collect** details conversationally — one or two questions at a time:
   - Meeting title / purpose
   - Duration (offer: 30 min, 45 min, 1 hour, or custom — the user's default \
is pre-set but they can override it)
   - Preferred dates (today, tomorrow, this week, specific date)
3. **Check calendars**: call `get_connected_calendars`. If none are connected, \
ask the user to connect one via the sidebar and wait.
4. **Fetch slots**: call `get_available_slots`. Do not specify `work_start` or \
`work_end` unless the user has explicitly told you different hours in this conversation; \
leave them unset and the user's saved schedule will be used automatically.
5. **Present slots** in a numbered, human-readable list (use the `display` field).
6. **Confirm** the chosen slot and all details with the user before booking.
7. **Book**: call `create_appointment` only after explicit user confirmation.
8. **Confirm** the booking with a friendly summary including the calendar link.

## Rules
- Never book without explicit confirmation ("yes", "book it", "confirm", etc.).
- Never suggest or book a time in the past.
- Present at most 6 slots. If none are found, suggest a wider date range.
- Always show times in the user's timezone.
- If a tool returns `needs_reconnect: true`, tell the user their calendar \
connection has expired and ask them to reconnect from the sidebar.
- Keep responses concise and friendly. Use markdown sparingly.
"""


class ClaudeAIService(AIService):
    """Claude-powered AI service with tool-use for calendar scheduling."""

    def __init__(
        self,
        session_store: AbstractSessionStore,
        scheduling_service: SchedulingService,
        profile_service: ProfileService,
    ) -> None:
        self._store = session_store
        self._scheduler = scheduling_service
        self._profile_svc = profile_service
        self._settings = get_settings()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)

    def process_message(
        self, session_id: str, user_message: str, timezone: str = "UTC"
    ) -> ProcessResult:
        self._store.set_timezone(session_id, timezone)
        self._store.append_message(
            session_id, {"role": "user", "content": user_message}
        )

        try:
            text, needs_reconnect = self._agentic_loop(session_id)
        except AppError as exc:
            logger.warning("AppError during agentic loop: %s", exc.message)
            text = f"I ran into an issue: {exc.message} Please try again."
            needs_reconnect = set()
        except anthropic.APIError as exc:
            logger.error("Anthropic API error: %s", exc)
            raise AIServiceError(str(exc)) from exc

        return ProcessResult(
            text=text,
            needs_reconnect_providers=sorted(needs_reconnect),
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _agentic_loop(self, session_id: str) -> tuple[str, set[str]]:
        """Drive the Claude tool-use loop; accumulate reconnect providers."""
        all_needs_reconnect: set[str] = set()
        session = self._store.get(session_id)

        while True:
            response = self._client.messages.create(
                model=self._settings.claude_model,
                max_tokens=2048,
                system=_build_system_prompt(),
                tools=TOOLS,
                messages=session.conversation_history,
            )

            self._store.append_message(
                session_id,
                {"role": "assistant", "content": response.content},
            )

            if response.stop_reason == "end_turn":
                text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                return text, all_needs_reconnect

            if response.stop_reason == "tool_use":
                tool_results, needs_reconnect = self._execute_tools(
                    session_id, response.content
                )
                all_needs_reconnect.update(needs_reconnect)
                self._store.append_message(
                    session_id,
                    {"role": "user", "content": tool_results},
                )
                session = self._store.get(session_id)
                continue

            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            return "Something unexpected happened. Please try again.", all_needs_reconnect

    def _execute_tools(
        self, session_id: str, content_blocks: list
    ) -> tuple[list[dict[str, Any]], set[str]]:
        """Execute all tool_use blocks; return results and reconnect provider set."""
        results: list[dict[str, Any]] = []
        needs_reconnect: set[str] = set()

        for block in content_blocks:
            if block.type != "tool_use":
                continue

            logger.info("Tool call: %s | input=%s", block.name, block.input)

            try:
                output = self._dispatch(session_id, block.name, block.input)
                content = json.dumps(output)
                is_error = False
            except CalendarAuthError as exc:
                # Surface to the frontend so the reconnect prompt appears
                needs_reconnect.add(exc.provider)
                content = json.dumps({
                    "error": exc.message,
                    "needs_reconnect": True,
                    "provider": exc.provider,
                })
                is_error = True
                logger.warning("CalendarAuthError for %s: %s", exc.provider, exc.message)
            except AppError as exc:
                content = json.dumps({"error": exc.message})
                is_error = True
                logger.warning("Tool %s failed: %s", block.name, exc.message)
            except Exception as exc:
                content = json.dumps({"error": f"Unexpected error: {exc}"})
                is_error = True
                logger.exception("Unexpected error in tool %s", block.name)

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": is_error,
            })

        return results, needs_reconnect

    def _dispatch(self, session_id: str, tool_name: str, tool_input: dict) -> dict:
        session = self._store.get(session_id)
        tz = session.timezone or "UTC"

        if tool_name == "get_connected_calendars":
            return self._scheduler.get_connected_calendars(session_id)

        if tool_name == "get_available_slots":
            # Resolve work hours: tool override → user profile → global default
            profile = self._profile_svc.get_or_create(session.user_id) if session.user_id else None
            default_start = profile.work_start if profile else "09:00"
            default_end = profile.work_end if profile else "17:00"
            return self._scheduler.get_available_slots(
                session_id=session_id,
                date_from=tool_input["date_from"],
                date_to=tool_input["date_to"],
                duration_minutes=tool_input["duration_minutes"],
                timezone_str=tool_input.get("timezone", tz),
                calendar_provider=tool_input["calendar_provider"],
                work_start=tool_input.get("work_start") or default_start,
                work_end=tool_input.get("work_end") or default_end,
            )

        if tool_name == "create_appointment":
            return self._scheduler.create_appointment(
                session_id=session_id,
                title=tool_input["title"],
                start_datetime=tool_input["start_datetime"],
                end_datetime=tool_input["end_datetime"],
                timezone_str=tool_input.get("timezone", tz),
                calendar_provider=tool_input["calendar_provider"],
                description=tool_input.get("description", ""),
                attendees=tool_input.get("attendees", []),
            )

        raise ValueError(f"Unknown tool: {tool_name}")
