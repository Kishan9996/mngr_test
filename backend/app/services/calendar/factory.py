"""Factory for creating CalendarProvider instances.

Design pattern: Factory Method — callers receive an abstract CalendarProvider
without knowing which concrete class is instantiated.
"""

from __future__ import annotations

from app.core.exceptions import UnsupportedProviderError
from app.models.appointment import CalendarTokens
from app.services.calendar.base import CalendarProvider
from app.services.calendar.google_calendar import GoogleCalendarProvider
from app.services.calendar.outlook_calendar import OutlookCalendarProvider

# Registry maps provider name → concrete class
_REGISTRY: dict[str, type[CalendarProvider]] = {
    "google": GoogleCalendarProvider,
    "outlook": OutlookCalendarProvider,
}


class CalendarProviderFactory:
    """Creates and returns a CalendarProvider for the given provider name."""

    @staticmethod
    def create(provider: str, tokens: CalendarTokens) -> CalendarProvider:
        key = provider.lower().strip()
        cls = _REGISTRY.get(key)
        if cls is None:
            raise UnsupportedProviderError(provider)
        return cls(tokens)

    @staticmethod
    def create_unauthenticated(provider: str) -> CalendarProvider:
        """Create a provider instance for OAuth URL generation (no tokens needed)."""
        from app.models.appointment import CalendarTokens

        dummy = CalendarTokens(provider=provider, access_token="")
        return CalendarProviderFactory.create(provider, dummy)

    @staticmethod
    def supported_providers() -> list[str]:
        return list(_REGISTRY.keys())
