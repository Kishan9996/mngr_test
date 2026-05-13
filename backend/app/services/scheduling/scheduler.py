"""Scheduling orchestration service.

Bridges the AI tool calls with the calendar provider implementations.
Returns serialisable dicts so the Claude service can embed them in tool results.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytz

from app.core.exceptions import CalendarAuthError, PastBookingError, SlotNotAvailableError
from app.models.appointment import AvailabilityRequest, CalendarEvent, CalendarTokens
from app.services.calendar.factory import CalendarProviderFactory
from app.services.session.session_store import SessionStore

logger = logging.getLogger(__name__)


class SchedulingService:
    """Executes calendar tool calls on behalf of the AI agent."""

    def __init__(self, session_store: SessionStore) -> None:
        self._store = session_store

    # ── Tool handlers ──────────────────────────────────────────────────────────

    def get_available_slots(
        self,
        session_id: str,
        date_from: str,
        date_to: str,
        duration_minutes: int,
        timezone_str: str,
        calendar_provider: str,
        work_start: str = "09:00",
        work_end: str = "17:00",
        max_slots: int = 6,
    ) -> dict:
        tokens = self._require_tokens(session_id, calendar_provider)
        provider = CalendarProviderFactory.create(calendar_provider, tokens)

        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz=tz)
        from_dt = tz.localize(datetime.fromisoformat(date_from))
        to_dt = tz.localize(datetime.fromisoformat(date_to))

        # Never search in the past — clamp silently so Claude doesn't need to know
        if from_dt < now:
            from_dt = now
        if to_dt < now:
            to_dt = now

        request = AvailabilityRequest(
            date_from=from_dt,
            date_to=to_dt,
            duration_minutes=duration_minutes,
            timezone=timezone_str,
            work_start=work_start,
            work_end=work_end,
            calendar_provider=calendar_provider,
            max_slots=max_slots,
        )

        slots = provider.find_available_slots(request)

        if not slots:
            return {
                "slots": [],
                "message": "No available slots found in the requested range.",
                "timezone": timezone_str,
            }

        return {
            "slots": [
                {
                    "index": i + 1,
                    "start": slot.start.isoformat(),
                    "end": slot.end.isoformat(),
                    "display": slot.display_label,
                }
                for i, slot in enumerate(slots)
            ],
            "timezone": timezone_str,
        }

    def create_appointment(
        self,
        session_id: str,
        title: str,
        start_datetime: str,
        end_datetime: str,
        timezone_str: str,
        calendar_provider: str,
        description: str = "",
        attendees: list[str] | None = None,
    ) -> dict:
        tokens = self._require_tokens(session_id, calendar_provider)
        provider = CalendarProviderFactory.create(calendar_provider, tokens)

        start_utc = datetime.fromisoformat(start_datetime).astimezone(timezone.utc)
        end_utc = datetime.fromisoformat(end_datetime).astimezone(timezone.utc)

        if start_utc <= datetime.now(tz=timezone.utc):
            raise PastBookingError()

        # Verify the slot is still free (optimistic check)
        busy = provider.get_busy_times(
            start_utc.date(), end_utc.date(), timezone_str
        )
        from app.models.appointment import TimeRange

        proposed = TimeRange(start=start_utc, end=end_utc)
        if any(proposed.overlaps(b) for b in busy):
            raise SlotNotAvailableError()

        event = CalendarEvent(
            title=title,
            start=start_utc,
            end=end_utc,
            timezone=timezone_str,
            description=description,
            attendees=attendees or [],
        )
        created = provider.create_event(event)

        logger.info(
            "Appointment created | provider=%s event_id=%s",
            calendar_provider,
            created.event_id,
        )

        return {
            "success": True,
            "event_id": created.event_id,
            "title": created.title,
            "start": created.start.isoformat(),
            "end": created.end.isoformat(),
            "timezone": created.timezone,
            "calendar_link": created.html_link,
            "provider": created.provider,
        }

    def get_connected_calendars(self, session_id: str) -> dict:
        providers = self._store.connected_providers(session_id)
        return {
            "connected_providers": providers,
            "message": (
                f"Connected: {', '.join(providers)}" if providers
                else "No calendars connected. Please connect Google or Outlook first."
            ),
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _require_tokens(self, session_id: str, provider: str) -> CalendarTokens:
        tokens = self._store.get_tokens(session_id, provider)
        if tokens is None:
            raise CalendarAuthError(provider)
        return tokens
