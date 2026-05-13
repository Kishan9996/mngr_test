"""Calendar OAuth routes.

Flow for each provider:
  1. GET /auth/{provider}?session_id=...  (authenticated) → redirect to provider
  2. Provider redirects to GET /auth/{provider}/callback?code=...&state={session_id}
  3. Backend exchanges code, saves tokens by user_id, redirects to frontend.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytz
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.deps import get_current_user, get_session_store
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.chat import UserPayload
from app.services.calendar.factory import CalendarProviderFactory
from app.services.session.abstract_store import AbstractSessionStore

router = APIRouter(prefix="/calendar", tags=["calendar"])
logger = logging.getLogger(__name__)
settings = get_settings()

SUPPORTED = CalendarProviderFactory.supported_providers()


@router.get("/auth/{provider}")
def start_oauth(
    provider: str,
    session_id: str = Query(..., description="Client session ID"),
    current_user: UserPayload = Depends(get_current_user),
    store: AbstractSessionStore = Depends(get_session_store),
) -> RedirectResponse:
    """Redirect the browser to the provider's OAuth consent page.

    The auth cookie is sent automatically by the browser, so no token param needed.
    """
    _check_provider(provider)
    store.link_session_to_user(session_id, current_user.user_id)
    p = CalendarProviderFactory.create_unauthenticated(provider)
    url = p.get_auth_url(state=session_id)
    logger.info("Starting OAuth | provider=%s user=%s", provider, current_user.user_id)
    return RedirectResponse(url=url)


@router.get("/auth/{provider}/callback")
def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(..., description="Session ID passed as OAuth state"),
    store: AbstractSessionStore = Depends(get_session_store),
) -> RedirectResponse:
    """Exchange the authorisation code for tokens and store them in the session."""
    _check_provider(provider)
    session_id = state

    try:
        p = CalendarProviderFactory.create_unauthenticated(provider)
        tokens = p.exchange_code(code)
        store.save_tokens(session_id, tokens)
        logger.info("OAuth complete | provider=%s session=%s", provider, session_id)
    except AppError as exc:
        logger.error("OAuth callback error: %s", exc.message)
        redirect_url = f"{settings.frontend_url}?error={exc.message}&provider={provider}"
        return RedirectResponse(url=redirect_url)
    except Exception:
        logger.exception("Unexpected OAuth callback error for %s", provider)
        redirect_url = f"{settings.frontend_url}?error=Unexpected+error&provider={provider}"
        return RedirectResponse(url=redirect_url)

    redirect_url = (
        f"{settings.frontend_url}"
        f"?calendar_connected={provider}"
        f"&session_id={session_id}"
    )
    return RedirectResponse(url=redirect_url)


@router.delete("/disconnect/{provider}")
def disconnect_calendar(
    provider: str,
    session_id: str = Query(...),
    current_user: UserPayload = Depends(get_current_user),
    store: AbstractSessionStore = Depends(get_session_store),
) -> JSONResponse:
    """Remove the stored tokens for this provider."""
    _check_provider(provider)
    store.remove_tokens(session_id, provider)
    logger.info("Disconnected | provider=%s user=%s", provider, current_user.user_id)
    return JSONResponse({"success": True, "provider": provider})


@router.get("/providers")
def list_providers() -> JSONResponse:
    return JSONResponse({"providers": SUPPORTED})


@router.get("/events")
def get_events(
    session_id: str = Query(...),
    days_ahead: int = Query(30, ge=1, le=90, description="How many days ahead to fetch"),
    timezone: str = Query("UTC", description="IANA timezone for display"),
    current_user: UserPayload = Depends(get_current_user),
    store: AbstractSessionStore = Depends(get_session_store),
) -> JSONResponse:
    """Return upcoming events from ALL calendars across all connected providers."""
    connected = store.connected_providers(session_id)
    if not connected:
        return JSONResponse({"events": [], "fetched_from": []})

    tz = pytz.timezone(timezone)
    today = datetime.now(tz=tz).date()
    end_date = today + timedelta(days=days_ahead)

    all_events = []
    fetched_from = []

    for provider_name in connected:
        tokens = store.get_tokens(session_id, provider_name)
        if not tokens:
            continue
        try:
            provider = CalendarProviderFactory.create(provider_name, tokens)
            events = provider.get_upcoming_events(today, end_date, timezone)
            all_events.extend(events)
            fetched_from.append(provider_name)
        except Exception as exc:
            logger.warning("Failed to fetch events from %s: %s", provider_name, exc)

    all_events.sort(key=lambda e: e.start)

    return JSONResponse({
        "events": [
            {
                "event_id": e.event_id,
                "title": e.title,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "is_all_day": e.is_all_day,
                "is_recurring": e.is_recurring,
                "description": e.description,
                "attendees": e.attendees,
                "calendar_name": e.calendar_name,
                "calendar_id": e.calendar_id,
                "provider": e.provider,
                "html_link": e.html_link,
            }
            for e in all_events
        ],
        "fetched_from": fetched_from,
    })


def _check_provider(provider: str) -> None:
    if provider not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
