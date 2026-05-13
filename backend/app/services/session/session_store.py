"""In-memory session store (Singleton) — used in tests and as fallback.

In production, DBSessionStore is wired in via deps.py.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Optional

from app.core.exceptions import SessionNotFoundError
from app.models.appointment import CalendarTokens
from app.models.chat import SessionData
from app.services.session.abstract_store import AbstractSessionStore


class SessionStore(AbstractSessionStore):
    """Thread-safe, in-memory implementation (Singleton pattern)."""

    _instance: Optional["SessionStore"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "SessionStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._sessions: dict[str, SessionData] = {}
                    inst._sessions_lock = threading.Lock()
                    cls._instance = inst
        return cls._instance

    # ── AbstractSessionStore implementation ───────────────────────────────────

    def get_or_create(self, session_id: str) -> SessionData:
        with self._sessions_lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionData(session_id=session_id)
            session = self._sessions[session_id]
            session.last_active = datetime.utcnow()
            return session

    def get(self, session_id: str) -> SessionData:
        with self._sessions_lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(session_id)
            session.last_active = datetime.utcnow()
            return session

    def get_or_create_for_user(self, user_id: str) -> str:
        """In-memory: use user_id itself as the session_id (simpler for tests)."""
        self.get_or_create(user_id)
        return user_id

    def link_session_to_user(self, session_id: str, user_id: str) -> None:
        session = self.get_or_create(session_id)
        with self._sessions_lock:
            if session.user_id and session.user_id != user_id:
                from app.core.exceptions import AppError
                raise AppError("Session belongs to a different user.", status_code=403)
            session.user_id = user_id

    def save_tokens(self, session_id: str, tokens: CalendarTokens) -> None:
        session = self.get_or_create(session_id)
        with self._sessions_lock:
            session.calendar_tokens[tokens.provider] = tokens

    def get_tokens(self, session_id: str, provider: str) -> Optional[CalendarTokens]:
        try:
            session = self.get(session_id)
        except SessionNotFoundError:
            return None
        return session.calendar_tokens.get(provider)

    def remove_tokens(self, session_id: str, provider: str) -> None:
        try:
            session = self.get(session_id)
        except SessionNotFoundError:
            return
        with self._sessions_lock:
            session.calendar_tokens.pop(provider, None)

    def connected_providers(self, session_id: str) -> list[str]:
        try:
            session = self.get(session_id)
        except SessionNotFoundError:
            return []
        return list(session.calendar_tokens.keys())

    def append_message(self, session_id: str, message: dict) -> None:
        session = self.get_or_create(session_id)
        with self._sessions_lock:
            session.conversation_history.append(message)

    def set_timezone(self, session_id: str, timezone: str) -> None:
        session = self.get_or_create(session_id)
        with self._sessions_lock:
            session.timezone = timezone

    # ── Maintenance ────────────────────────────────────────────────────────────

    def evict_stale(self, max_age_hours: int = 24) -> int:
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        with self._sessions_lock:
            stale = [sid for sid, s in self._sessions.items() if s.last_active < cutoff]
            for sid in stale:
                del self._sessions[sid]
        return len(stale)
