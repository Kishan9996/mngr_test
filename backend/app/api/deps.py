"""FastAPI dependency providers (Dependency Injection)."""

from functools import lru_cache

from fastapi import Depends, Header, HTTPException

from app.models.chat import UserPayload
from app.services.ai.claude_service import ClaudeAIService
from app.services.auth.auth_service import AuthService
from app.services.profile.profile_service import ProfileService
from app.services.scheduling.scheduler import SchedulingService
from app.services.session.abstract_store import AbstractSessionStore
from app.services.session.db_session_store import DBSessionStore


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
    authorization: str = Header(None, alias="Authorization"),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPayload:
    """Extract and validate the Bearer JWT from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")
    token = authorization[len("Bearer "):]
    try:
        return auth_service.decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
