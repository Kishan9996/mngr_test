from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_ai_service, get_current_user, get_session_store
from app.core.exceptions import AIServiceError, AppError
from app.models.chat import (
    CalendarStatusResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    UserPayload,
)
from app.services.ai.claude_service import ClaudeAIService
from app.services.session.abstract_store import AbstractSessionStore

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/message", response_model=ChatMessageResponse)
def send_message(
    body: ChatMessageRequest,
    current_user: UserPayload = Depends(get_current_user),
    ai_service: ClaudeAIService = Depends(get_ai_service),
    store: AbstractSessionStore = Depends(get_session_store),
) -> ChatMessageResponse:
    """Send a user message and receive the AI assistant's reply."""
    # Bind this session to the authenticated user (idempotent)
    store.link_session_to_user(body.session_id, current_user.user_id)

    try:
        result = ai_service.process_message(
            session_id=body.session_id,
            user_message=body.message,
            timezone=body.timezone,
        )
    except AIServiceError as exc:
        logger.error("AI service error: %s", exc.message)
        raise HTTPException(status_code=503, detail=exc.message)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception:
        logger.exception("Unexpected error processing message")
        raise HTTPException(status_code=500, detail="Internal server error")

    connected = store.connected_providers(body.session_id)
    return ChatMessageResponse(
        session_id=body.session_id,
        response=result.text,
        connected_providers=connected,
        needs_reconnect_providers=result.needs_reconnect_providers,
    )


@router.get("/status", response_model=CalendarStatusResponse)
def get_status(
    session_id: str,
    current_user: UserPayload = Depends(get_current_user),
    store: AbstractSessionStore = Depends(get_session_store),
) -> CalendarStatusResponse:
    """Return which calendar providers are connected for this session."""
    connected = store.connected_providers(session_id)
    return CalendarStatusResponse(
        session_id=session_id,
        connected_providers=connected,
    )
