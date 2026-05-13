"""SQLAlchemy ORM models for persistent storage."""

from __future__ import annotations

from datetime import datetime

from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    calendar_tokens: Mapped[list["CalendarTokenRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    profile: Mapped[Optional["UserProfile"]] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="session", order_by="ConversationMessage.id", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_sessions.session_id"), nullable=False, index=True
    )
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped["UserSession"] = relationship(back_populates="messages")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    work_start: Mapped[str] = mapped_column(String(5), default="09:00", nullable=False)
    work_end: Mapped[str] = mapped_column(String(5), default="17:00", nullable=False)
    default_duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="profile")


class CalendarTokenRecord(Base):
    __tablename__ = "calendar_tokens"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extra_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="calendar_tokens")
