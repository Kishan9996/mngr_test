from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.schemas import ExtractionSession


class AbstractSessionStore(ABC):

    @abstractmethod
    def get_or_create_for_user(self, user_id: str, org_id: int) -> str:
        """Return the canonical session_id for this user, creating one if needed."""

    @abstractmethod
    def get(self, session_id: str) -> ExtractionSession: ...

    @abstractmethod
    def append_message(self, session_id: str, message: dict) -> None: ...

    @abstractmethod
    def cache_customer(self, session_id: str, customer: dict) -> None:
        """Persist a resolved customer lookup so Claude doesn't repeat it."""

    @abstractmethod
    def clear_history(self, session_id: str) -> None: ...
