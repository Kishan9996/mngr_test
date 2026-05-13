"""FastAPI dependency providers."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Request

from app.core.security import TokenPayload, decode_access_token
from app.services.ai.claude_extraction_service import ClaudeExtractionService
from app.services.auth.auth_service import AuthService
from app.services.cache.query_cache import QueryCache
from app.services.session.abstract_store import AbstractSessionStore
from app.services.session.db_session_store import DBSessionStore

_ACCESS_COOKIE = "access_token"
_REFRESH_COOKIE = "refresh_token"


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService()


@lru_cache
def get_session_store() -> AbstractSessionStore:
    return DBSessionStore()


@lru_cache
def get_query_cache() -> QueryCache:
    return QueryCache()


@lru_cache
def get_ai_service() -> ClaudeExtractionService:
    return ClaudeExtractionService(get_session_store(), get_query_cache())


def get_current_user(request: Request) -> TokenPayload:
    """Validate access token from httpOnly cookie."""
    token = request.cookies.get(_ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        return decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")


def require_admin(payload: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if payload.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return payload
