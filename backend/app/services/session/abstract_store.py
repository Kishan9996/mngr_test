from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.models.appointment import CalendarTokens
from app.models.chat import SessionData


class AbstractSessionStore(ABC):
    """Interface that both the in-memory and DB-backed stores must satisfy."""

    @abstractmethod
    def get_or_create(self, session_id: str) -> SessionData: ...

    @abstractmethod
    def get(self, session_id: str) -> SessionData: ...

    @abstractmethod
    def link_session_to_user(self, session_id: str, user_id: str) -> None:
        """Associate a session with a user account (creates the record if needed)."""

    @abstractmethod
    def save_tokens(self, session_id: str, tokens: CalendarTokens) -> None: ...

    @abstractmethod
    def get_tokens(self, session_id: str, provider: str) -> Optional[CalendarTokens]: ...

    @abstractmethod
    def remove_tokens(self, session_id: str, provider: str) -> None: ...

    @abstractmethod
    def connected_providers(self, session_id: str) -> list[str]: ...

    @abstractmethod
    def append_message(self, session_id: str, message: dict) -> None: ...

    @abstractmethod
    def set_timezone(self, session_id: str, timezone: str) -> None: ...
