from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── API Request / Response models (Pydantic) ─────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Minimum 8 characters")


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str


class UserPayload(BaseModel):
    user_id: str
    email: str


class ChatMessageRequest(BaseModel):
    session_id: str = Field(..., description="Unique client session identifier (UUID4)")
    message: str = Field(..., min_length=1, max_length=4096)
    timezone: str = Field("UTC", description="IANA timezone string, e.g. 'Europe/London'")


class ChatMessageResponse(BaseModel):
    session_id: str
    response: str
    connected_providers: list[str] = Field(default_factory=list)
    needs_reconnect_providers: list[str] = Field(default_factory=list)


class UserProfileResponse(BaseModel):
    work_start: str
    work_end: str
    default_duration_minutes: int
    timezone: str
    onboarding_completed: bool


class UserProfileUpdate(BaseModel):
    work_start: str | None = None
    work_end: str | None = None
    default_duration_minutes: int | None = None
    timezone: str | None = None
    onboarding_completed: bool | None = None


class CalendarStatusResponse(BaseModel):
    session_id: str
    connected_providers: list[str]


# ─── Internal AI service result ───────────────────────────────────────────────

@dataclass
class ProcessResult:
    """Returned by ClaudeAIService.process_message."""
    text: str
    needs_reconnect_providers: list[str] = field(default_factory=list)


# ─── Internal session data (dataclass) ────────────────────────────────────────

@dataclass
class SessionData:
    session_id: str
    user_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    # Claude conversation history in Anthropic message-list format
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    # provider name -> CalendarTokens (used by in-memory store; DB store queries DB directly)
    calendar_tokens: dict[str, Any] = field(default_factory=dict)
    timezone: str = "UTC"
