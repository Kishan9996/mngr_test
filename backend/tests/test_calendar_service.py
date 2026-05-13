"""Unit tests for calendar providers and the factory."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import CalendarAPIError, UnsupportedProviderError
from app.models.appointment import CalendarEvent, CalendarTokens, TimeRange
from app.services.calendar.factory import CalendarProviderFactory
from app.services.calendar.google_calendar import GoogleCalendarProvider
from app.services.calendar.outlook_calendar import OutlookCalendarProvider


# ── Factory tests ──────────────────────────────────────────────────────────────

class TestCalendarProviderFactory:
    def test_creates_google_provider(self):
        tokens = CalendarTokens(provider="google", access_token="tok")
        provider = CalendarProviderFactory.create("google", tokens)
        assert isinstance(provider, GoogleCalendarProvider)

    def test_creates_outlook_provider(self):
        tokens = CalendarTokens(provider="outlook", access_token="tok")
        provider = CalendarProviderFactory.create("outlook", tokens)
        assert isinstance(provider, OutlookCalendarProvider)

    def test_raises_for_unknown_provider(self):
        tokens = CalendarTokens(provider="unknown", access_token="tok")
        with pytest.raises(UnsupportedProviderError):
            CalendarProviderFactory.create("unknown", tokens)

    def test_supported_providers_includes_google_and_outlook(self):
        providers = CalendarProviderFactory.supported_providers()
        assert "google" in providers
        assert "outlook" in providers


# ── Google Calendar provider tests ────────────────────────────────────────────

class TestGoogleCalendarProvider:
    @pytest.fixture
    def provider(self):
        tokens = CalendarTokens(
            provider="google",
            access_token="fake",
            refresh_token="fake-refresh",
            extra={"token_uri": "https://oauth2.googleapis.com/token"},
        )
        return GoogleCalendarProvider(tokens)

    def test_get_auth_url_contains_google_domain(self, provider):
        url = provider.get_auth_url(state="test-state")
        assert "accounts.google.com" in url
        assert "test-state" in url

    @patch("app.services.calendar.google_calendar.build")
    @patch("app.services.calendar.google_calendar.Request")
    def test_get_busy_times_returns_time_ranges(self, mock_request, mock_build, provider):
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.freebusy().query().execute.return_value = {
            "calendars": {
                "primary": {
                    "busy": [
                        {
                            "start": "2025-01-15T09:00:00Z",
                            "end": "2025-01-15T10:00:00Z",
                        }
                    ]
                }
            }
        }

        result = provider.get_busy_times(
            date(2025, 1, 15), date(2025, 1, 15), "UTC"
        )

        assert len(result) == 1
        assert isinstance(result[0], TimeRange)
        assert result[0].start.hour == 9

    @patch("app.services.calendar.google_calendar.build")
    @patch("app.services.calendar.google_calendar.Request")
    def test_create_event_returns_created_event(self, mock_request, mock_build, provider):
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.events().insert().execute.return_value = {
            "id": "event-123",
            "summary": "Team Sync",
            "htmlLink": "https://calendar.google.com/event?id=event-123",
        }

        event = CalendarEvent(
            title="Team Sync",
            start=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 15, 11, 0, tzinfo=timezone.utc),
            timezone="UTC",
        )
        result = provider.create_event(event)

        assert result.event_id == "event-123"
        assert result.title == "Team Sync"
        assert result.provider == "google"

    @patch("app.services.calendar.google_calendar.build")
    @patch("app.services.calendar.google_calendar.Request")
    def test_get_busy_times_raises_on_api_error(self, mock_request, mock_build, provider):
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.freebusy().query().execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b"Forbidden"
        )

        with pytest.raises(CalendarAPIError):
            provider.get_busy_times(date(2025, 1, 15), date(2025, 1, 15), "UTC")


# ── Outlook Calendar provider tests ──────────────────────────────────────────

class TestOutlookCalendarProvider:
    @pytest.fixture
    def provider(self):
        tokens = CalendarTokens(
            provider="outlook",
            access_token="fake-token",
            refresh_token="fake-refresh",
        )
        return OutlookCalendarProvider(tokens)

    def test_get_auth_url_contains_microsoft_domain(self, provider):
        url = provider.get_auth_url(state="test-state")
        assert "login.microsoftonline.com" in url
        assert "test-state" in url

    @patch("app.services.calendar.outlook_calendar.httpx.Client")
    def test_get_busy_times_returns_time_ranges(self, mock_client_cls, provider):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {
                    "start": {"dateTime": "2025-01-15T09:00:00", "timeZone": "UTC"},
                    "end": {"dateTime": "2025-01-15T10:00:00", "timeZone": "UTC"},
                    "showAs": "busy",
                }
            ]
        }
        mock_client.get.return_value = mock_response

        result = provider.get_busy_times(
            date(2025, 1, 15), date(2025, 1, 15), "UTC"
        )

        assert len(result) == 1
        assert isinstance(result[0], TimeRange)

    @patch("app.services.calendar.outlook_calendar.httpx.Client")
    def test_create_event_returns_created_event(self, mock_client_cls, provider):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "outlook-event-456",
            "subject": "Team Sync",
            "webLink": "https://outlook.com/event/456",
        }
        mock_client.post.return_value = mock_response

        event = CalendarEvent(
            title="Team Sync",
            start=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 15, 11, 0, tzinfo=timezone.utc),
            timezone="UTC",
        )
        result = provider.create_event(event)

        assert result.event_id == "outlook-event-456"
        assert result.provider == "outlook"
