"""Google Calendar provider (Strategy concrete implementation).

Uses the official google-api-python-client library.
Free/busy queries and event listing span ALL calendars the user has,
not just "primary", fixing the primary-calendar-only limitation.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import pytz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import get_settings
from app.core.exceptions import CalendarAPIError, CalendarAuthError
from app.models.appointment import (
    CalendarEvent,
    CalendarEventItem,
    CalendarInfo,
    CalendarTokens,
    CreatedEvent,
    TimeRange,
)
from app.services.calendar.base import CalendarProvider
from app.utils.retry import with_retry

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


class GoogleCalendarProvider(CalendarProvider):
    provider_name = "google"

    def __init__(self, tokens: CalendarTokens) -> None:
        super().__init__(tokens)
        self._settings = get_settings()

    # ── OAuth ──────────────────────────────────────────────────────────────────

    def get_auth_url(self, state: str) -> str:
        flow = self._make_flow()
        url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        return url

    def exchange_code(self, code: str) -> CalendarTokens:
        flow = self._make_flow()
        flow.fetch_token(code=code)
        return self._creds_to_tokens(flow.credentials)

    def refresh_tokens(self) -> CalendarTokens:
        creds = self._build_credentials()
        if not creds.valid:
            creds.refresh(Request())
        return self._creds_to_tokens(creds)

    # ── Multi-calendar: list ───────────────────────────────────────────────────

    @with_retry(max_attempts=3, backoff_base=1.0, retryable=(HttpError, ConnectionError, TimeoutError))
    def list_calendars(self) -> list[CalendarInfo]:
        self._ensure_tokens()
        service = self._build_service()
        try:
            result = service.calendarList().list(minAccessRole="reader").execute()
        except HttpError as exc:
            raise CalendarAPIError("google", str(exc)) from exc

        calendars = []
        for item in result.get("items", []):
            calendars.append(CalendarInfo(
                calendar_id=item["id"],
                name=item.get("summary", item["id"]),
                provider="google",
                is_primary=item.get("primary", False),
            ))
        return calendars

    # ── Multi-calendar: upcoming events ───────────────────────────────────────

    @with_retry(max_attempts=3, backoff_base=1.0, retryable=(HttpError, ConnectionError, TimeoutError))
    def get_upcoming_events(
        self, start: date, end: date, timezone: str
    ) -> list[CalendarEventItem]:
        self._ensure_tokens()
        service = self._build_service()
        tz = pytz.timezone(timezone)

        start_dt = tz.localize(datetime.combine(start, datetime.min.time())).isoformat()
        end_dt = tz.localize(datetime.combine(end, datetime.max.time())).isoformat()

        calendars = self.list_calendars()
        all_events: list[CalendarEventItem] = []

        for cal in calendars:
            try:
                result = service.events().list(
                    calendarId=cal.calendar_id,
                    timeMin=start_dt,
                    timeMax=end_dt,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=250,
                ).execute()
            except HttpError as exc:
                # Skip calendars we can't access rather than aborting the whole list
                logger.warning("Skipping calendar %s: %s", cal.calendar_id, exc)
                continue

            for item in result.get("items", []):
                if item.get("status") == "cancelled":
                    continue
                all_events.append(self._parse_event(item, cal, timezone))

        all_events.sort(key=lambda e: e.start)
        return all_events

    # ── Busy times (now uses ALL calendars) ───────────────────────────────────

    @with_retry(max_attempts=3, backoff_base=1.0, retryable=(HttpError, ConnectionError, TimeoutError))
    def get_busy_times(
        self, start: date, end: date, timezone: str
    ) -> list[TimeRange]:
        self._ensure_tokens()
        service = self._build_service()

        start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=pytz.UTC)
        end_dt = datetime.combine(end, datetime.max.time()).replace(tzinfo=pytz.UTC)

        # Collect all calendar IDs the user has access to
        try:
            cal_list = service.calendarList().list(minAccessRole="reader").execute()
            items = [{"id": c["id"]} for c in cal_list.get("items", [])]
        except HttpError:
            items = [{"id": "primary"}]  # graceful fallback

        body = {
            "timeMin": start_dt.isoformat(),
            "timeMax": end_dt.isoformat(),
            "items": items or [{"id": "primary"}],
            "timeZone": "UTC",
        }

        try:
            result = service.freebusy().query(body=body).execute()
        except HttpError as exc:
            raise CalendarAPIError("google", str(exc)) from exc

        busy: list[TimeRange] = []
        for cal_data in result.get("calendars", {}).values():
            for period in cal_data.get("busy", []):
                busy.append(TimeRange(
                    start=datetime.fromisoformat(period["start"].replace("Z", "+00:00")),
                    end=datetime.fromisoformat(period["end"].replace("Z", "+00:00")),
                ))
        return busy

    # ── Create event ──────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, backoff_base=1.0, retryable=(HttpError, ConnectionError, TimeoutError))
    def create_event(self, event: CalendarEvent) -> CreatedEvent:
        self._ensure_tokens()
        service = self._build_service()
        tz_obj = pytz.timezone(event.timezone)

        body: dict[str, Any] = {
            "summary": event.title,
            "description": event.description,
            "start": {
                "dateTime": event.start.astimezone(tz_obj).isoformat(),
                "timeZone": event.timezone,
            },
            "end": {
                "dateTime": event.end.astimezone(tz_obj).isoformat(),
                "timeZone": event.timezone,
            },
        }
        if event.attendees:
            body["attendees"] = [{"email": e} for e in event.attendees]

        try:
            created = service.events().insert(calendarId="primary", body=body).execute()
        except HttpError as exc:
            raise CalendarAPIError("google", str(exc)) from exc

        return CreatedEvent(
            event_id=created["id"],
            title=created.get("summary", event.title),
            start=event.start,
            end=event.end,
            timezone=event.timezone,
            html_link=created.get("htmlLink", ""),
            provider="google",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_flow(self) -> Flow:
        s = self._settings
        client_config = {
            "web": {
                "client_id": s.google_client_id,
                "client_secret": s.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [s.google_redirect_uri],
            }
        }
        return Flow.from_client_config(
            client_config, scopes=SCOPES, redirect_uri=s.google_redirect_uri
        )

    def _build_credentials(self) -> OAuthCredentials:
        t = self._tokens
        return OAuthCredentials(
            token=t.access_token,
            refresh_token=t.refresh_token,
            token_uri=t.extra.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=self._settings.google_client_id,
            client_secret=self._settings.google_client_secret,
        )

    def _build_service(self):
        creds = self._build_credentials()
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            self._tokens = self._creds_to_tokens(creds)
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def _creds_to_tokens(self, creds: OAuthCredentials) -> CalendarTokens:
        expiry = creds.expiry
        return CalendarTokens(
            provider="google",
            access_token=creds.token or "",
            refresh_token=creds.refresh_token,
            expires_at=expiry.replace(tzinfo=timezone.utc) if expiry else None,
            extra={"token_uri": creds.token_uri or "https://oauth2.googleapis.com/token"},
        )

    @staticmethod
    def _parse_event(
        item: dict, cal: CalendarInfo, tz_name: str
    ) -> CalendarEventItem:
        is_all_day = "date" in item.get("start", {})
        if is_all_day:
            start = datetime.fromisoformat(item["start"]["date"]).replace(tzinfo=pytz.UTC)
            end = datetime.fromisoformat(item["end"]["date"]).replace(tzinfo=pytz.UTC)
        else:
            raw_start = item["start"].get("dateTime", "")
            raw_end = item["end"].get("dateTime", "")
            start = datetime.fromisoformat(raw_start.replace("Z", "+00:00")).astimezone(pytz.UTC)
            end = datetime.fromisoformat(raw_end.replace("Z", "+00:00")).astimezone(pytz.UTC)

        return CalendarEventItem(
            event_id=item["id"],
            title=item.get("summary", "(No title)"),
            start=start,
            end=end,
            timezone=tz_name,
            calendar_name=cal.name,
            calendar_id=cal.calendar_id,
            provider="google",
            html_link=item.get("htmlLink", ""),
            is_all_day=is_all_day,
        )
