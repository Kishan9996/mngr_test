"""Chat route: message processing and history retrieval."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_ai_service, get_current_user, get_session_store
from app.core.exceptions import SessionNotFoundError
from app.core.security import TokenPayload
from app.models.schemas import (
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatMessageResponse,
)
from app.services.ai.claude_extraction_service import ClaudeExtractionService
from app.services.session.abstract_store import AbstractSessionStore

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def send_message(
    body: ChatMessageRequest,
    payload: TokenPayload     = Depends(get_current_user),
    store:   AbstractSessionStore = Depends(get_session_store),
    ai_svc:  ClaudeExtractionService = Depends(get_ai_service),
) -> ChatMessageResponse:
    # Resolve or create canonical session for this user
    session_id = body.session_id or store.get_or_create_for_user(payload.user_id, payload.org_id)

    # Guard: session must belong to this user's org (prevents cross-org access)
    try:
        session = store.get(session_id)
    except SessionNotFoundError:
        session_id = store.get_or_create_for_user(payload.user_id, payload.org_id)
        session = store.get(session_id)

    if session.org_id != payload.org_id:
        raise HTTPException(status_code=403, detail="Session does not belong to your organisation.")

    reply = ai_svc.process_message(session_id, body.message)
    return ChatMessageResponse(reply=reply, session_id=session_id)


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
def get_history(
    session_id: str,
    payload:    TokenPayload      = Depends(get_current_user),
    store:      AbstractSessionStore = Depends(get_session_store),
) -> ChatHistoryResponse:
    try:
        session = store.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.org_id != payload.org_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    messages = [
        ChatHistoryMessage(role=m["role"], content=m["content"])
        for m in session.conversation_history
        if isinstance(m.get("content"), str)   # expose only text turns
    ]
    return ChatHistoryResponse(session_id=session_id, messages=messages)


@router.delete("/history/{session_id}", status_code=204, response_model=None)
def clear_history(
    session_id: str,
    payload:    TokenPayload      = Depends(get_current_user),
    store:      AbstractSessionStore = Depends(get_session_store),
) -> None:
    try:
        session = store.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.org_id != payload.org_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    store.clear_history(session_id)
