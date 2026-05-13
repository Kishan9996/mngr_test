"""SQLite-backed session store.

One canonical session per user (latest wins).
Conversation history in session_messages.
Resolved-entity cache in chat_sessions.context_json.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.exceptions import SessionNotFoundError
from app.models.db import ChatSession, SessionMessage
from app.models.schemas import ExtractionSession
from app.services.session.abstract_store import AbstractSessionStore

logger = logging.getLogger(__name__)


class DBSessionStore(AbstractSessionStore):

    def get_or_create_for_user(self, user_id: str, org_id: int) -> str:
        with SessionLocal() as db:
            record = db.scalar(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.last_active.desc())
            )
            if record:
                record.last_active = datetime.utcnow().isoformat()
                db.commit()
                return record.session_id

            sid = str(uuid.uuid4())
            db.add(ChatSession(session_id=sid, user_id=user_id, org_id=org_id))
            db.commit()
            logger.info("Created session %s for user %s org %d", sid, user_id, org_id)
            return sid

    def get(self, session_id: str) -> ExtractionSession:
        with SessionLocal() as db:
            record = db.get(ChatSession, session_id)
            if record is None:
                raise SessionNotFoundError(session_id)

            record.last_active = datetime.utcnow().isoformat()
            db.commit()

            messages = [
                json.loads(m.content_json)
                for m in db.scalars(
                    select(SessionMessage)
                    .where(SessionMessage.session_id == session_id)
                    .order_by(SessionMessage.id)
                ).all()
            ]

            context = json.loads(record.context_json or "{}")
            resolved: dict[int, dict] = {
                int(k): v for k, v in context.get("resolved_customers", {}).items()
            }

            return ExtractionSession(
                session_id=session_id,
                user_id=record.user_id,
                org_id=record.org_id,
                conversation_history=messages,
                resolved_customers=resolved,
            )

    def append_message(self, session_id: str, message: dict) -> None:
        with SessionLocal() as db:
            db.add(SessionMessage(
                session_id=session_id,
                content_json=_serialize(message),
            ))
            db.commit()

    def cache_customer(self, session_id: str, customer: dict) -> None:
        cid = customer.get("id")
        if cid is None:
            return
        with SessionLocal() as db:
            record = db.get(ChatSession, session_id)
            if not record:
                return
            context = json.loads(record.context_json or "{}")
            resolved = context.get("resolved_customers", {})
            resolved[str(cid)] = customer
            context["resolved_customers"] = resolved
            record.context_json = json.dumps(context)
            db.commit()

    def clear_history(self, session_id: str) -> None:
        with SessionLocal() as db:
            db.query(SessionMessage)\
              .filter(SessionMessage.session_id == session_id)\
              .delete()
            record = db.get(ChatSession, session_id)
            if record:
                record.context_json = "{}"
            db.commit()
        logger.info("Cleared history for session %s", session_id)


def _serialize(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, list):
        serialized = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in content
        ]
        return json.dumps({"role": message["role"], "content": serialized})
    return json.dumps({"role": message["role"], "content": content})
