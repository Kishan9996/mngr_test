"""FastAPI dependency providers (Dependency Injection)."""

from functools import lru_cache

from app.services.ai.claude_service import ClaudeAIService
from app.services.scheduling.scheduler import SchedulingService
from app.services.session.session_store import SessionStore


@lru_cache
def get_session_store() -> SessionStore:
    return SessionStore()


@lru_cache
def get_scheduling_service() -> SchedulingService:
    return SchedulingService(get_session_store())


@lru_cache
def get_ai_service() -> ClaudeAIService:
    return ClaudeAIService(get_session_store(), get_scheduling_service())
