"""Claude AI service with tool-use for calendar scheduling.

Design patterns used:
- Strategy: implements AIService interface — swap with another LLM without
  touching callers.
- Command: each tool call from Claude is dispatched through a command registry
  (_TOOL_HANDLERS) keeping the agentic loop clean.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.core.config import get_settings
from app.core.exceptions import AIServiceError, AppError
from app.services.ai.base import AIService
from app.services.scheduling.scheduler import SchedulingService
from app.services.session.session_store import SessionStore

logger = logging.getLogger(__name__)

# ── Tool definitions fed to the Claude API ────────────────────────────────────

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
                "date_from": {
                    "type": "string",
                    "description": "Start date in ISO format YYYY-MM-DD (inclusive).",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date in ISO format YYYY-MM-DD (inclusive).",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Appointment duration in minutes (e.g. 30, 60).",
                },
                "calendar_provider": {
                    "type": "string",
                    "enum": ["google", "outlook"],
                    "description": "Which calendar to check.",
                },
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone, e.g. 'Europe/London'. Defaults to 'UTC'.",
                },
                "work_start": {
                    "type": "string",
                    "description": "Working hours start in HH:MM format. Defaults to '09:00'.",
                },
                "work_end": {
                    "type": "string",
                    "description": "Working hours end in HH:MM format. Defaults to '17:00'.",
                },
            },
            "required": [
                "date_from", "date_to", "duration_minutes", "calendar_provider",
            ],
        },
    },
    {
        "name": "create_appointment",
        "description": (
            "Book an appointment on the user's calendar. Only call after the user "
            "has explicitly confirmed the time slot and title. Verify the details "
            "once more with the user before calling this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title / subject of the appointment.",
                },
                "start_datetime": {
                    "type": "string",
                    "description": "Start in ISO 8601 format with timezone offset.",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "End in ISO 8601 format with timezone offset.",
                },
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone for the appointment.",
                },
                "calendar_provider": {
                    "type": "string",
                    "enum": ["google", "outlook"],
                },
                "description": {
                    "type": "string",
                    "description": "Optional description / agenda for the appointment.",
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of attendee email addresses.",
                },
            },
            "required": [
                "title", "start_datetime", "end_datetime",
                "timezone", "calendar_provider",
            ],
        },
    },
]

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a friendly and efficient AI scheduling assistant. \
Your sole purpose is to help users book appointments on their calendar.

## Workflow
1. **Greet** the user and ask what they'd like to schedule.
2. **Collect** details conversationally — one or two questions at a time:
   - Meeting title / purpose
   - Duration (offer: 30 min, 45 min, 1 hour, or custom)
   - Preferred dates (today, tomorrow, this week, specific date)
3. **Check calendars**: first call `get_connected_calendars`. If none are \
connected, ask the user to connect one via the sidebar and wait.
4. **Fetch slots**: call `get_available_slots` with the collected preferences.
5. **Present slots** in a numbered, human-readable list (use the `display` field).
6. **Confirm** the chosen slot and all details with the user before booking.
7. **Book**: call `create_appointment` only after explicit user confirmation.
8. **Confirm** the booking with a friendly summary including the calendar link.

## Rules
- Never book without explicit confirmation ("yes", "book it", "confirm", etc.).
- Present at most 6 slots. If none are found, suggest a wider date range.
- Always show times in the user's timezone.
- If a tool fails with a calendar auth error, tell the user to reconnect the \
calendar from the sidebar.
- Keep responses concise and friendly. Use markdown sparingly.
"""


class ClaudeAIService(AIService):
    """Concrete AI service powered by Claude with tool-use for calendar actions."""

    def __init__(
        self,
        session_store: SessionStore,
        scheduling_service: SchedulingService,
    ) -> None:
        self._store = session_store
        self._scheduler = scheduling_service
        self._settings = get_settings()
        self._client = anthropic.Anthropic(
            api_key=self._settings.anthropic_api_key
        )

    def process_message(
        self, session_id: str, user_message: str, timezone: str = "UTC"
    ) -> str:
        """Run the agentic loop: user turn → tool calls → final assistant reply."""
        session = self._store.get_or_create(session_id)
        self._store.set_timezone(session_id, timezone)

        # Append the new user message to history
        self._store.append_message(
            session_id, {"role": "user", "content": user_message}
        )

        try:
            reply = self._agentic_loop(session_id)
        except AppError as exc:
            logger.warning("AppError during agentic loop: %s", exc.message)
            reply = f"I ran into an issue: {exc.message} Please try again."
        except anthropic.APIError as exc:
            logger.error("Anthropic API error: %s", exc)
            raise AIServiceError(str(exc)) from exc

        return reply

    # ── Private ────────────────────────────────────────────────────────────────

    def _agentic_loop(self, session_id: str) -> str:
        """Drive the Claude tool-use loop until a final text response is produced."""
        session = self._store.get(session_id)

        while True:
            response = self._client.messages.create(
                model=self._settings.claude_model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=session.conversation_history,
            )

            # Append assistant response (may contain tool_use blocks)
            self._store.append_message(
                session_id,
                {"role": "assistant", "content": response.content},
            )

            if response.stop_reason == "end_turn":
                # Extract the final text block
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            if response.stop_reason == "tool_use":
                tool_results = self._execute_tools(session_id, response.content)
                self._store.append_message(
                    session_id,
                    {"role": "user", "content": tool_results},
                )
                # Re-fetch session for the updated history
                session = self._store.get(session_id)
                continue

            # Unexpected stop reason
            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            return "Something unexpected happened. Please try again."

    def _execute_tools(
        self, session_id: str, content_blocks: list
    ) -> list[dict[str, Any]]:
        """Execute all tool_use blocks and return a list of tool_result dicts."""
        results: list[dict[str, Any]] = []

        for block in content_blocks:
            if block.type != "tool_use":
                continue

            tool_name: str = block.name
            tool_input: dict = block.input
            tool_use_id: str = block.id

            logger.info("Executing tool: %s | input=%s", tool_name, tool_input)

            try:
                output = self._dispatch(session_id, tool_name, tool_input)
                content = json.dumps(output)
                is_error = False
            except AppError as exc:
                content = json.dumps({"error": exc.message})
                is_error = True
                logger.warning("Tool %s failed: %s", tool_name, exc.message)
            except Exception as exc:
                content = json.dumps({"error": f"Unexpected error: {exc}"})
                is_error = True
                logger.exception("Unexpected error in tool %s", tool_name)

            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content,
                    "is_error": is_error,
                }
            )

        return results

    def _dispatch(
        self, session_id: str, tool_name: str, tool_input: dict
    ) -> dict:
        """Route a tool call to the appropriate SchedulingService method."""
        session = self._store.get(session_id)
        tz = session.timezone or "UTC"

        if tool_name == "get_connected_calendars":
            return self._scheduler.get_connected_calendars(session_id)

        if tool_name == "get_available_slots":
            return self._scheduler.get_available_slots(
                session_id=session_id,
                date_from=tool_input["date_from"],
                date_to=tool_input["date_to"],
                duration_minutes=tool_input["duration_minutes"],
                timezone_str=tool_input.get("timezone", tz),
                calendar_provider=tool_input["calendar_provider"],
                work_start=tool_input.get("work_start", "09:00"),
                work_end=tool_input.get("work_end", "17:00"),
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
