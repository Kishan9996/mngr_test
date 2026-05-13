"""Abstract base for calendar providers.

Design patterns used:
- Strategy: each provider (Google, Outlook) is a concrete strategy implementing
  this interface so callers only depend on the abstraction.
- Template Method: `find_available_slots` defines the algorithm skeleton;
  subclasses override `get_busy_times` and `create_event`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Optional

from app.core.exceptions import CalendarAuthError
from app.models.appointment import (
    AvailabilityRequest,
    CalendarEvent,
    CalendarTokens,
    CreatedEvent,
    TimeRange,
    TimeSlot,
)
from app.utils.date_utils import filter_available_slots, generate_candidate_slots

logger = logging.getLogger(__name__)


class CalendarProvider(ABC):
    """Strategy interface — all calendar integrations must implement this."""

    provider_name: str = ""

    def __init__(self, tokens: CalendarTokens) -> None:
        self._tokens = tokens

    # ── Abstract methods (Strategy hook points) ────────────────────────────────

    @abstractmethod
    def get_busy_times(
        self, start: date, end: date, timezone: str
    ) -> list[TimeRange]:
        """Return busy intervals in UTC for the given date range (inclusive)."""

    @abstractmethod
    def create_event(self, event: CalendarEvent) -> CreatedEvent:
        """Create a calendar event and return the persisted result."""

    @abstractmethod
    def get_auth_url(self, state: str) -> str:
        """Return the OAuth 2.0 authorisation URL for this provider."""

    @abstractmethod
    def exchange_code(self, code: str) -> CalendarTokens:
        """Exchange an authorisation code for tokens."""

    @abstractmethod
    def refresh_tokens(self) -> CalendarTokens:
        """Refresh the access token using the stored refresh token."""

    # ── Template Method ────────────────────────────────────────────────────────

    def find_available_slots(self, request: AvailabilityRequest) -> list[TimeSlot]:
        """Template method: fetch busy times → generate candidates → filter."""
        logger.info(
            "Finding slots | provider=%s from=%s to=%s duration=%dmin",
            self.provider_name,
            request.date_from.date(),
            request.date_to.date(),
            request.duration_minutes,
        )

        busy = self.get_busy_times(
            request.date_from.date(), request.date_to.date(), request.timezone
        )

        all_slots: list[TimeSlot] = []
        current = request.date_from.date()
        while current <= request.date_to.date():
            day_candidates = list(
                generate_candidate_slots(
                    on_date=current,
                    duration_minutes=request.duration_minutes,
                    work_start=request.work_start,
                    work_end=request.work_end,
                    tz_name=request.timezone,
                )
            )
            available = filter_available_slots(day_candidates, busy)
            all_slots.extend(available)
            current += timedelta(days=1)

        result = all_slots[: request.max_slots]
        logger.info("Found %d available slots", len(result))
        return result

    # ── Token helpers ──────────────────────────────────────────────────────────

    def _ensure_tokens(self) -> None:
        if not self._tokens or not self._tokens.access_token:
            raise CalendarAuthError(self.provider_name)

    def update_tokens(self, tokens: CalendarTokens) -> None:
        self._tokens = tokens
