"""Outlook Calendar provider via Microsoft Graph API (Strategy concrete impl).

Authentication uses the MSAL library (confidential client flow).
Access tokens are obtained via the authorisation-code grant and refreshed
automatically by MSAL's token cache.
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
from app.utils.retry import with_retry
from app.models.appointment import (
    CalendarEvent,
    CalendarTokens,
    CreatedEvent,
    TimeRange,
)
from app.services.calendar.base import CalendarProvider

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Calendars.ReadWrite", "offline_access"]


class OutlookCalendarProvider(CalendarProvider):
    provider_name = "outlook"

    def __init__(self, tokens: CalendarTokens) -> None:
        super().__init__(tokens)
        self._settings = get_settings()

    # ── OAuth helpers ──────────────────────────────────────────────────────────

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

    # ── Strategy implementation ────────────────────────────────────────────────

    @with_retry(max_attempts=3, backoff_base=1.0, retryable=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, ConnectionError))
    def get_busy_times(
        self, start: date, end: date, timezone: str
    ) -> list[TimeRange]:
        self._ensure_tokens()

        start_dt = datetime.combine(start, datetime.min.time()).replace(
            tzinfo=pytz.UTC
        )
        end_dt = datetime.combine(end, datetime.max.time()).replace(
            tzinfo=pytz.UTC
        )

        url = f"{GRAPH_BASE}/me/calendarView"
        params = {
            "startDateTime": start_dt.isoformat(),
            "endDateTime": end_dt.isoformat(),
            "$select": "start,end,showAs",
            "$top": "100",
        }

        try:
            response = self._graph_get(url, params=params)
        except httpx.HTTPStatusError as exc:
            raise CalendarAPIError("outlook", str(exc)) from exc

        busy: list[TimeRange] = []
        for item in response.get("value", []):
            if item.get("showAs", "busy") in ("busy", "tentative", "oof"):
                s_raw = item["start"]["dateTime"]
                e_raw = item["end"]["dateTime"]
                busy.append(
                    TimeRange(
                        start=self._parse_graph_dt(s_raw),
                        end=self._parse_graph_dt(e_raw),
                    )
                )
        return busy

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

    # ── Private helpers ────────────────────────────────────────────────────────

    def _make_msal_app(self) -> msal.ConfidentialClientApplication:
        s = self._settings
        authority = f"https://login.microsoftonline.com/{s.outlook_tenant_id}"
        return msal.ConfidentialClientApplication(
            s.outlook_client_id,
            authority=authority,
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
        """Return a valid access token, refreshing if necessary."""
        now = datetime.now(tz=timezone.utc)
        expires_at = self._tokens.expires_at
        if expires_at and now >= expires_at:
            self._tokens = self.refresh_tokens()
        return self._tokens.access_token

    @staticmethod
    def _parse_graph_dt(raw: str) -> datetime:
        """Parse Graph API datetime strings (may or may not have tz suffix)."""
        raw = raw.rstrip("Z")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _result_to_tokens(result: dict) -> CalendarTokens:
        import time as _time

        expires_in = result.get("expires_in", 3600)
        expires_at = datetime.fromtimestamp(
            _time.time() + expires_in, tz=timezone.utc
        )
        return CalendarTokens(
            provider="outlook",
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
            expires_at=expires_at,
        )
