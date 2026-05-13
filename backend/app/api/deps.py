"""FastAPI dependency providers (Dependency Injection)."""

from functools import lru_cache

from fastapi import Depends, HTTPException, Request

from app.models.chat import UserPayload
from app.services.ai.claude_service import ClaudeAIService
from app.services.auth.auth_service import AuthService
from app.services.profile.profile_service import ProfileService
from app.services.scheduling.scheduler import SchedulingService
from app.services.session.abstract_store import AbstractSessionStore
from app.services.session.db_session_store import DBSessionStore

_COOKIE_NAME = "auth_token"


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService()


@lru_cache
def get_profile_service() -> ProfileService:
    return ProfileService()


@lru_cache
def get_session_store() -> AbstractSessionStore:
    return DBSessionStore()


@lru_cache
def get_scheduling_service() -> SchedulingService:
    return SchedulingService(get_session_store())


@lru_cache
def get_ai_service() -> ClaudeAIService:
    return ClaudeAIService(get_session_store(), get_scheduling_service(), get_profile_service())


def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPayload:
    """Read the JWT from the httpOnly cookie and validate it."""
    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        return auth_service.decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
