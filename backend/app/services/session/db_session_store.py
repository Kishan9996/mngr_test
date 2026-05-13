"""SQLite-backed session store via SQLAlchemy.

Calendar tokens are stored per USER (not per session) so they survive
across sessions, backend restarts, and multiple devices.
Conversation history is stored per session.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

import uuid

from app.core.database import SessionLocal
from app.core.exceptions import AppError, SessionNotFoundError
from app.models.appointment import CalendarTokens
from app.models.chat import SessionData
from app.models.db import CalendarTokenRecord, ConversationMessage, UserSession
from app.services.session.abstract_store import AbstractSessionStore

logger = logging.getLogger(__name__)


class DBSessionStore(AbstractSessionStore):
    """Persistent session store backed by SQLite (production default)."""

    # ── AbstractSessionStore implementation ───────────────────────────────────

    def get_or_create(self, session_id: str) -> SessionData:
        with SessionLocal() as db:
            record = db.get(UserSession, session_id)
            if record:
                record.last_active = datetime.utcnow()
                db.commit()
                return self._build_session_data(db, record)
            # Session not yet linked to a user — return an empty shell
            return SessionData(session_id=session_id)

    def get(self, session_id: str) -> SessionData:
        with SessionLocal() as db:
            record = db.get(UserSession, session_id)
            if record is None:
                # Session may exist as an unlinked in-flight request — return empty
                return SessionData(session_id=session_id)
            record.last_active = datetime.utcnow()
            db.commit()
            return self._build_session_data(db, record)

    def get_or_create_for_user(self, user_id: str) -> str:
        """Return this user's canonical session_id, creating one if they have none.

        One user always maps to the same session so that history and tokens
        are isolated per account across all browsers and devices.
        """
        with SessionLocal() as db:
            record = db.scalar(
                select(UserSession)
                .where(UserSession.user_id == user_id)
                .order_by(UserSession.last_active.desc())
            )
            if record:
                record.last_active = datetime.utcnow()
                db.commit()
                return record.session_id
            # First login for this user — create their canonical session
            session_id = str(uuid.uuid4())
            db.add(UserSession(session_id=session_id, user_id=user_id))
            db.commit()
            logger.info("Created canonical session %s for user %s", session_id, user_id)
            return session_id

    def link_session_to_user(self, session_id: str, user_id: str) -> None:
        """Bind a session to a user. Hard-fails if the session already belongs
        to a *different* user — prevents cross-user data leakage."""
        with SessionLocal() as db:
            record = db.get(UserSession, session_id)
            if record is None:
                db.add(UserSession(session_id=session_id, user_id=user_id))
                logger.info("Linked session %s → user %s", session_id, user_id)
            elif record.user_id != user_id:
                logger.error(
                    "Session hijack attempt: session %s belongs to user %s, "
                    "not %s", session_id, record.user_id, user_id,
                )
                raise AppError("Invalid session for this account.", status_code=403)
            else:
                record.last_active = datetime.utcnow()
            db.commit()

    def save_tokens(self, session_id: str, tokens: CalendarTokens) -> None:
        user_id = self._get_user_id(session_id)
        if user_id is None:
            logger.warning("Cannot save tokens: session %s has no linked user", session_id)
            return
        with SessionLocal() as db:
            stmt = (
                sqlite_insert(CalendarTokenRecord)
                .values(
                    user_id=user_id,
                    provider=tokens.provider,
                    access_token=tokens.access_token,
                    refresh_token=tokens.refresh_token,
                    expires_at=tokens.expires_at,
                    extra_json=json.dumps(tokens.extra),
                    updated_at=datetime.utcnow(),
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "provider"],
                    set_={
                        "access_token": tokens.access_token,
                        "refresh_token": tokens.refresh_token,
                        "expires_at": tokens.expires_at,
                        "extra_json": json.dumps(tokens.extra),
                        "updated_at": datetime.utcnow(),
                    },
                )
            )
            db.execute(stmt)
            db.commit()

    def get_tokens(self, session_id: str, provider: str) -> Optional[CalendarTokens]:
        user_id = self._get_user_id(session_id)
        if user_id is None:
            return None
        with SessionLocal() as db:
            record = db.scalar(
                select(CalendarTokenRecord).where(
                    CalendarTokenRecord.user_id == user_id,
                    CalendarTokenRecord.provider == provider,
                )
            )
            return self._record_to_tokens(record) if record else None

    def remove_tokens(self, session_id: str, provider: str) -> None:
        user_id = self._get_user_id(session_id)
        if user_id is None:
            return
        with SessionLocal() as db:
            record = db.scalar(
                select(CalendarTokenRecord).where(
                    CalendarTokenRecord.user_id == user_id,
                    CalendarTokenRecord.provider == provider,
                )
            )
            if record:
                db.delete(record)
                db.commit()

    def connected_providers(self, session_id: str) -> list[str]:
        user_id = self._get_user_id(session_id)
        if user_id is None:
            return []
        with SessionLocal() as db:
            rows = db.scalars(
                select(CalendarTokenRecord.provider).where(
                    CalendarTokenRecord.user_id == user_id
                )
            ).all()
            return list(rows)

    def clear_history(self, session_id: str) -> None:
        with SessionLocal() as db:
            db.query(ConversationMessage)\
              .filter(ConversationMessage.session_id == session_id)\
              .delete()
            db.commit()
        logger.info("Cleared conversation history for session %s", session_id)

    def append_message(self, session_id: str, message: dict) -> None:
        with SessionLocal() as db:
            content_json = _serialize_message(message)
            db.add(ConversationMessage(session_id=session_id, content_json=content_json))
            db.commit()

    def set_timezone(self, session_id: str, timezone: str) -> None:
        with SessionLocal() as db:
            record = db.get(UserSession, session_id)
            if record:
                record.timezone = timezone
                db.commit()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_user_id(self, session_id: str) -> Optional[str]:
        with SessionLocal() as db:
            record = db.get(UserSession, session_id)
            return record.user_id if record else None

    def _build_session_data(self, db: Session, record: UserSession) -> SessionData:
        messages = [
            json.loads(m.content_json)
            for m in db.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.session_id == record.session_id)
                .order_by(ConversationMessage.id)
            ).all()
        ]
        return SessionData(
            session_id=record.session_id,
            user_id=record.user_id,
            timezone=record.timezone,
            conversation_history=messages,
            last_active=record.last_active,
        )

    @staticmethod
    def _record_to_tokens(record: CalendarTokenRecord) -> CalendarTokens:
        expires_at = record.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return CalendarTokens(
            provider=record.provider,
            access_token=record.access_token,
            refresh_token=record.refresh_token,
            expires_at=expires_at,
            extra=json.loads(record.extra_json or "{}"),
        )


def _serialize_message(message: dict) -> str:
    """Serialize a Claude API message dict to JSON, handling Pydantic model content blocks."""
    content = message.get("content")
    if isinstance(content, list):
        serialized = []
        for item in content:
            if hasattr(item, "model_dump"):
                serialized.append(item.model_dump())
            elif isinstance(item, dict):
                serialized.append(item)
            else:
                serialized.append({"type": "text", "text": str(item)})
        return json.dumps({"role": message["role"], "content": serialized})
    return json.dumps({"role": message["role"], "content": content})
