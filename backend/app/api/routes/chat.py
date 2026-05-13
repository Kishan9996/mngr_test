from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from app.api.deps import get_ai_service, get_current_user, get_session_store
from app.core.limiter import limit_chat
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


@router.post("/message", response_model=ChatMessageResponse, dependencies=[Depends(limit_chat)])
def send_message(
    request: Request,
    body: ChatMessageRequest,
    current_user: UserPayload = Depends(get_current_user),
    ai_service: ClaudeAIService = Depends(get_ai_service),
    store: AbstractSessionStore = Depends(get_session_store),
) -> ChatMessageResponse:
    store.link_session_to_user(body.session_id, current_user.user_id)

    try:
        result = ai_service.process_message(
            session_id=body.session_id,
            user_message=body.message,
            timezone=body.timezone,
        )
    except AIServiceError as exc:
        logger.error("AI service error: %s", exc.message)
        raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable.")
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception:
        logger.exception("Unexpected error processing message")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

    connected = store.connected_providers(body.session_id)
    return ChatMessageResponse(
        session_id=body.session_id,
        response=result.text,
        connected_providers=connected,
        needs_reconnect_providers=result.needs_reconnect_providers,
    )


@router.get("/status", response_model=CalendarStatusResponse)
def get_status(
    request: Request,
    session_id: str,
    current_user: UserPayload = Depends(get_current_user),
    store: AbstractSessionStore = Depends(get_session_store),
) -> CalendarStatusResponse:
    connected = store.connected_providers(session_id)
    return CalendarStatusResponse(session_id=session_id, connected_providers=connected)


@router.get("/history")
def get_history(
    request: Request,
    session_id: str,
    current_user: UserPayload = Depends(get_current_user),
    store: AbstractSessionStore = Depends(get_session_store),
) -> dict:
    """Return prior conversation messages in a frontend-renderable format.

    Filters out tool-use/tool-result blocks — only user and assistant text
    messages are returned.
    """
    store.link_session_to_user(session_id, current_user.user_id)
    session = store.get_or_create(session_id)
    messages = []

    for msg in session.conversation_history:
        role = msg.get("role")
        content = msg.get("content")

        if role == "user" and isinstance(content, str):
            messages.append({"role": "user", "content": content})

        elif role == "assistant":
            if isinstance(content, list):
                text = " ".join(
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ).strip()
                if text:
                    messages.append({"role": "assistant", "content": text})
            elif isinstance(content, str) and content.strip():
                messages.append({"role": "assistant", "content": content})

        # Skip tool-use / tool-result messages entirely

    return {"session_id": session_id, "messages": messages}
