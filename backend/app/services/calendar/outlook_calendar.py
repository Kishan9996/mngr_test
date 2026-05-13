"""Outlook Calendar provider via Microsoft Graph API (Strategy concrete impl).

Event listing and busy-time checks span ALL user calendars, not just the default.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
import msal
import pytz

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
from app.utils.cache import calendar_list_cache
from app.utils.retry import with_retry

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Calendars.ReadWrite", "offline_access"]


class OutlookCalendarProvider(CalendarProvider):
    provider_name = "outlook"

    def __init__(self, tokens: CalendarTokens) -> None:
        super().__init__(tokens)
        self._settings = get_settings()

    # ── OAuth ──────────────────────────────────────────────────────────────────

    def get_auth_url(self, state: str) -> str:
        s = self._settings
        params = {
            "client_id": s.outlook_client_id,
            "response_type": "code",
            "redirect_uri": s.outlook_redirect_uri,
            "scope": " ".join(SCOPES),
            "state": state,
            "response_mode": "query",
        }
        base = f"https://login.microsoftonline.com/{s.outlook_tenant_id}/oauth2/v2.0/authorize"
        return f"{base}?{urlencode(params)}"

    def exchange_code(self, code: str) -> CalendarTokens:
        app = self._make_msal_app()
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=SCOPES,
            redirect_uri=self._settings.outlook_redirect_uri,
        )
        if "error" in result:
            raise CalendarAuthError("outlook", result.get("error_description", ""))
        return self._result_to_tokens(result)

    def refresh_tokens(self) -> CalendarTokens:
        refresh_token = self._tokens.refresh_token
        if not refresh_token:
            raise CalendarAuthError("outlook", "No refresh token available.")
        app = self._make_msal_app()
        result = app.acquire_token_by_refresh_token(refresh_token, scopes=SCOPES)
        if "error" in result:
            raise CalendarAuthError("outlook", result.get("error_description", ""))
        return self._result_to_tokens(result)

    # ── Multi-calendar: list ───────────────────────────────────────────────────

    @with_retry(max_attempts=3, backoff_base=1.0, retryable=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, ConnectionError))
    def list_calendars(self) -> list[CalendarInfo]:
        self._ensure_tokens()
        cache_key = f"outlook:calendars:{self._tokens.access_token[:16]}"
        cached = calendar_list_cache.get(cache_key)
        if cached is not None:
            return [CalendarInfo(**item) for item in cached]

        try:
            result = self._graph_get(
                f"{GRAPH_BASE}/me/calendars",
                params={"$select": "id,name,isDefaultCalendar", "$top": "100"},
            )
        except httpx.HTTPStatusError as exc:
            raise CalendarAPIError("outlook", str(exc)) from exc

        calendars = [
            CalendarInfo(
                calendar_id=cal["id"],
                name=cal["name"],
                provider="outlook",
                is_primary=cal.get("isDefaultCalendar", False),
            )
            for cal in result.get("value", [])
        ]
        import dataclasses
        calendar_list_cache.set(cache_key, [dataclasses.asdict(c) for c in calendars])
        return calendars

    # ── Multi-calendar: upcoming events ───────────────────────────────────────

    @with_retry(max_attempts=3, backoff_base=1.0, retryable=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, ConnectionError))
    def get_upcoming_events(
        self, start: date, end: date, timezone: str
    ) -> list[CalendarEventItem]:
        self._ensure_tokens()
        tz = pytz.timezone(timezone)
        start_dt = tz.localize(datetime.combine(start, datetime.min.time())).isoformat()
        end_dt = tz.localize(datetime.combine(end, datetime.max.time())).isoformat()

        calendars = self.list_calendars()
        all_events: list[CalendarEventItem] = []

        for cal in calendars:
            try:
                result = self._graph_get(
                    f"{GRAPH_BASE}/me/calendars/{cal.calendar_id}/calendarView",
                    params={
                        "startDateTime": start_dt,
                        "endDateTime": end_dt,
                        "$select": "id,subject,start,end,webLink,isAllDay,type,body,attendees",
                        "$top": "250",
                    },
                )
            except httpx.HTTPStatusError as exc:
                logger.warning("Skipping calendar %s: %s", cal.calendar_id, exc)
                continue

            for item in result.get("value", []):
                all_events.append(self._parse_event(item, cal, timezone))

        all_events.sort(key=lambda e: e.start)
        return all_events

    # ── Busy times (uses calendarView which covers all calendars) ─────────────

    @with_retry(max_attempts=3, backoff_base=1.0, retryable=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, ConnectionError))
    def get_busy_times(
        self, start: date, end: date, timezone: str
    ) -> list[TimeRange]:
        self._ensure_tokens()
        start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=pytz.UTC)
        end_dt = datetime.combine(end, datetime.max.time()).replace(tzinfo=pytz.UTC)

        # calendarView aggregates ALL calendars by default
        try:
            response = self._graph_get(
                f"{GRAPH_BASE}/me/calendarView",
                params={
                    "startDateTime": start_dt.isoformat(),
                    "endDateTime": end_dt.isoformat(),
                    "$select": "start,end,showAs",
                    "$top": "250",
                },
            )
        except httpx.HTTPStatusError as exc:
            raise CalendarAPIError("outlook", str(exc)) from exc

        busy: list[TimeRange] = []
        for item in response.get("value", []):
            if item.get("showAs", "busy") in ("busy", "tentative", "oof"):
                busy.append(TimeRange(
                    start=self._parse_graph_dt(item["start"]["dateTime"]),
                    end=self._parse_graph_dt(item["end"]["dateTime"]),
                ))
        return busy

    # ── Create event ──────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, backoff_base=1.0, retryable=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, ConnectionError))
    def create_event(self, event: CalendarEvent) -> CreatedEvent:
        self._ensure_tokens()
        tz_obj = pytz.timezone(event.timezone)
        body: dict[str, Any] = {
            "subject": event.title,
            "body": {"contentType": "text", "content": event.description},
            "start": {
                "dateTime": event.start.astimezone(tz_obj).strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": event.timezone,
            },
            "end": {
                "dateTime": event.end.astimezone(tz_obj).strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": event.timezone,
            },
        }
        if event.attendees:
            body["attendees"] = [
                {"emailAddress": {"address": e}, "type": "required"}
                for e in event.attendees
            ]
        try:
            created = self._graph_post(f"{GRAPH_BASE}/me/events", json=body)
        except httpx.HTTPStatusError as exc:
            raise CalendarAPIError("outlook", str(exc)) from exc

        return CreatedEvent(
            event_id=created["id"],
            title=created.get("subject", event.title),
            start=event.start,
            end=event.end,
            timezone=event.timezone,
            html_link=created.get("webLink", ""),
            provider="outlook",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_msal_app(self) -> msal.ConfidentialClientApplication:
        s = self._settings
        return msal.ConfidentialClientApplication(
            s.outlook_client_id,
            authority=f"https://login.microsoftonline.com/{s.outlook_tenant_id}",
            client_credential=s.outlook_client_secret,
        )

    def _graph_get(self, url: str, params: dict | None = None) -> dict:
        token = self._get_valid_token()
        with httpx.Client() as client:
            resp = client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    def _graph_post(self, url: str, json: dict) -> dict:
        token = self._get_valid_token()
        with httpx.Client() as client:
            resp = client.post(
                url,
                json=json,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    def _get_valid_token(self) -> str:
        now = datetime.now(tz=timezone.utc)
        if self._tokens.expires_at and now >= self._tokens.expires_at:
            self._tokens = self.refresh_tokens()
        return self._tokens.access_token

    @staticmethod
    def _parse_graph_dt(raw: str) -> datetime:
        raw = raw.rstrip("Z")
        dt = datetime.fromisoformat(raw)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    @staticmethod
    def _result_to_tokens(result: dict) -> CalendarTokens:
        import time as _time
        expires_at = datetime.fromtimestamp(
            _time.time() + result.get("expires_in", 3600), tz=timezone.utc
        )
        return CalendarTokens(
            provider="outlook",
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
            expires_at=expires_at,
        )

    @staticmethod
    def _parse_event(
        item: dict, cal: CalendarInfo, tz_name: str
    ) -> CalendarEventItem:
        is_all_day = item.get("isAllDay", False)
        start = OutlookCalendarProvider._parse_graph_dt(item["start"]["dateTime"])
        end = OutlookCalendarProvider._parse_graph_dt(item["end"]["dateTime"])
        import re as _re

        event_type = item.get("type", "singleInstance")

        # Extract plain-text description from the body (may be HTML)
        body = item.get("body", {})
        raw_body = body.get("content", "")
        if body.get("contentType", "text") == "html":
            description = _re.sub(r"<[^>]+>", " ", raw_body)
            description = _re.sub(r"\s+", " ", description).strip()
        else:
            description = raw_body.strip()

        attendees = [
            a.get("emailAddress", {}).get("name") or a.get("emailAddress", {}).get("address", "")
            for a in item.get("attendees", [])
            if a.get("emailAddress", {}).get("address")
        ]

        return CalendarEventItem(
            event_id=item["id"],
            title=item.get("subject", "(No title)"),
            start=start.astimezone(pytz.UTC),
            end=end.astimezone(pytz.UTC),
            timezone=tz_name,
            calendar_name=cal.name,
            calendar_id=cal.calendar_id,
            provider="outlook",
            html_link=item.get("webLink", ""),
            is_all_day=is_all_day,
            is_recurring=event_type in ("occurrence", "seriesMaster"),
            description=description,
            attendees=attendees,
        )
