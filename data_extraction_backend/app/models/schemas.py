"""Pydantic request/response schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ───────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:     EmailStr
    password:  str
    org_name:  str           # creates a new org on first registration

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class UserInfo(BaseModel):
    user_id:  str
    email:    str
    org_id:   int
    org_name: str
    role:     str


# ── Chat ───────────────────────────────────────────────────────────────────────

class ChatMessageRequest(BaseModel):
    message:    str
    session_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    reply:      str
    session_id: str


class ChatHistoryMessage(BaseModel):
    role:    str
    content: Any


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages:   list[ChatHistoryMessage]


# ── Seed ───────────────────────────────────────────────────────────────────────

class SeedRequest(BaseModel):
    data_dir:       str    # absolute or relative path to CSV folder
    org_name:       str
    admin_email:    EmailStr
    admin_password: str

    @field_validator("admin_password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class SeedResponse(BaseModel):
    org_id:            int
    org_name:          str
    customers_created: int
    orders_created:    int
    tickets_created:   int
    message:           str


# ── Internal session dataclass (not serialised over the wire) ─────────────────

@dataclass
class ExtractionSession:
    session_id:         str
    user_id:            str
    org_id:             int
    conversation_history: list[dict]          = field(default_factory=list)
    resolved_customers:   dict[int, dict]     = field(default_factory=dict)
    last_active:          Optional[datetime]  = None
