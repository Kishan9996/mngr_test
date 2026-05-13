from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── API Request / Response models (Pydantic) ─────────────────────────────────

class ChatMessageRequest(BaseModel):
    session_id: str = Field(..., description="Unique client session identifier (UUID4)")
    message: str = Field(..., min_length=1, max_length=4096)
    timezone: str = Field("UTC", description="IANA timezone string, e.g. 'Europe/London'")


class ChatMessageResponse(BaseModel):
    session_id: str
    response: str
    connected_providers: list[str] = Field(default_factory=list)


class CalendarStatusResponse(BaseModel):
    session_id: str
    connected_providers: list[str]


# ─── Internal session data (dataclass) ────────────────────────────────────────

@dataclass
class SessionData:
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    # Claude conversation history in Anthropic message-list format
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    # provider name -> CalendarTokens
    calendar_tokens: dict[str, Any] = field(default_factory=dict)
    timezone: str = "UTC"
