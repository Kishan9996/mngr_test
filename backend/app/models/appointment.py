from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class TimeRange:
    """An immutable half-open interval [start, end) in UTC."""

    start: datetime
    end: datetime

    def overlaps(self, other: TimeRange) -> bool:
        return self.start < other.end and self.end > other.start


@dataclass(frozen=True)
class TimeSlot(TimeRange):
    """A candidate appointment slot with a human-readable label."""

    display_label: str = ""


@dataclass
class AvailabilityRequest:
    """Parameters collected from the user before querying the calendar."""

    date_from: datetime
    date_to: datetime
    duration_minutes: int
    timezone: str = "UTC"
    work_start: str = "09:00"   # HH:MM local time
    work_end: str = "17:00"     # HH:MM local time
    calendar_provider: str = "google"
    max_slots: int = 6


@dataclass
class CalendarEvent:
    """Provider-agnostic event to create."""

    title: str
    start: datetime              # UTC
    end: datetime                # UTC
    timezone: str = "UTC"
    description: str = ""
    attendees: list[str] = field(default_factory=list)


@dataclass
class CreatedEvent:
    """Result returned after a successful event creation."""

    event_id: str
    title: str
    start: datetime
    end: datetime
    timezone: str
    html_link: str
    provider: str


@dataclass
class CalendarTokens:
    """OAuth token bundle stored per provider in a session."""

    provider: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    # Provider-specific extras (e.g. token_uri for Google)
    extra: dict = field(default_factory=dict)
