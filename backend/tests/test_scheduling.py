"""Unit tests for SchedulingService and date utilities."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.exceptions import CalendarAuthError, PastBookingError, SlotNotAvailableError
from app.models.appointment import CalendarTokens, TimeRange
from app.services.scheduling.scheduler import SchedulingService
from app.services.session.session_store import SessionStore
from app.utils.date_utils import (
    filter_available_slots,
    generate_candidate_slots,
)


# ── Date utils ────────────────────────────────────────────────────────────────

class TestGenerateCandidateSlots:
    def test_yields_slots_within_working_hours(self):
        slots = list(
            generate_candidate_slots(
                on_date=date(2025, 1, 15),
                duration_minutes=60,
                work_start="09:00",
                work_end="17:00",
                tz_name="UTC",
            )
        )
        assert len(slots) > 0
        for slot in slots:
            assert slot.end <= slot.start.replace(hour=17, minute=0, second=0, microsecond=0)

    def test_no_slots_when_duration_exceeds_window(self):
        slots = list(
            generate_candidate_slots(
                on_date=date(2025, 1, 15),
                duration_minutes=600,
                work_start="09:00",
                work_end="10:00",
                tz_name="UTC",
            )
        )
        assert slots == []

    def test_slot_labels_are_populated(self):
        slots = list(
            generate_candidate_slots(
                on_date=date(2025, 1, 15),
                duration_minutes=30,
                work_start="09:00",
                work_end="10:00",
                tz_name="UTC",
            )
        )
        assert all(slot.display_label for slot in slots)


class TestFilterAvailableSlots:
    def test_filters_out_overlapping_slots(self):
        from app.models.appointment import TimeSlot

        busy = [
            TimeRange(
                start=datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc),
                end=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
            )
        ]
        slots = list(
            generate_candidate_slots(
                on_date=date(2025, 1, 15),
                duration_minutes=60,
                work_start="09:00",
                work_end="11:00",
                tz_name="UTC",
            )
        )
        available = filter_available_slots(slots, busy)
        for slot in available:
            # 9-10 should be gone; 10-11 should remain
            assert slot.start >= datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)

    def test_returns_all_when_no_busy(self):
        # Use a date far in the future so the past-slot filter never triggers
        future_date = (datetime.now(tz=timezone.utc) + timedelta(days=30)).date()
        slots = list(
            generate_candidate_slots(
                on_date=future_date,
                duration_minutes=60,
                work_start="09:00",
                work_end="12:00",
                tz_name="UTC",
            )
        )
        available = filter_available_slots(slots, [])
        assert len(available) == len(slots)


# ── SchedulingService ─────────────────────────────────────────────────────────

class TestSchedulingService:
    @pytest.fixture
    def service(self, store: SessionStore) -> SchedulingService:
        return SchedulingService(store)

    def test_get_connected_calendars_empty_session(self, service):
        result = service.get_connected_calendars("no-tokens-session")
        assert result["connected_providers"] == []

    def test_get_connected_calendars_with_google(
        self, service, session_with_google: str
    ):
        result = service.get_connected_calendars(session_with_google)
        assert "google" in result["connected_providers"]

    def test_get_available_slots_raises_when_not_connected(self, service):
        with pytest.raises(CalendarAuthError):
            service.get_available_slots(
                session_id="no-calendar-session",
                date_from="2025-01-15",
                date_to="2025-01-16",
                duration_minutes=60,
                timezone_str="UTC",
                calendar_provider="google",
            )

    def test_create_appointment_raises_when_not_connected(self, service):
        with pytest.raises(CalendarAuthError):
            service.create_appointment(
                session_id="no-calendar-session",
                title="Test",
                start_datetime="2025-01-15T10:00:00+00:00",
                end_datetime="2025-01-15T11:00:00+00:00",
                timezone_str="UTC",
                calendar_provider="google",
            )

    def test_get_available_slots_with_mocked_provider(
        self, service, session_with_google: str, mocker
    ):
        from app.models.appointment import TimeSlot

        mock_slot = TimeSlot(
            start=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 15, 11, 0, tzinfo=timezone.utc),
            display_label="Wednesday, Jan 15 · 10:00 AM – 11:00 AM UTC",
        )
        mocker.patch(
            "app.services.scheduling.scheduler.CalendarProviderFactory.create"
        ).return_value.find_available_slots.return_value = [mock_slot]

        result = service.get_available_slots(
            session_id=session_with_google,
            date_from="2025-01-15",
            date_to="2025-01-15",
            duration_minutes=60,
            timezone_str="UTC",
            calendar_provider="google",
        )

        assert len(result["slots"]) == 1
        assert result["slots"][0]["index"] == 1

    def test_create_appointment_raises_past_booking(self, service, session_with_google: str):
        with pytest.raises(PastBookingError):
            service.create_appointment(
                session_id=session_with_google,
                title="Test",
                start_datetime="2025-01-15T10:00:00+00:00",
                end_datetime="2025-01-15T11:00:00+00:00",
                timezone_str="UTC",
                calendar_provider="google",
            )

    def test_create_appointment_raises_slot_not_available(
        self, service, session_with_google: str, mocker
    ):
        # Use a future datetime so PastBookingError is not raised first
        future_start = datetime.now(tz=timezone.utc) + timedelta(days=1, hours=2)
        future_end = future_start + timedelta(hours=1)

        busy_range = TimeRange(start=future_start, end=future_end)
        mocker.patch(
            "app.services.scheduling.scheduler.CalendarProviderFactory.create"
        ).return_value.get_busy_times.return_value = [busy_range]

        with pytest.raises(SlotNotAvailableError):
            service.create_appointment(
                session_id=session_with_google,
                title="Test",
                start_datetime=future_start.isoformat(),
                end_datetime=future_end.isoformat(),
                timezone_str="UTC",
                calendar_provider="google",
            )
