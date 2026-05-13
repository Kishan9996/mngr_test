"""SQLAlchemy ORM models — mirrors schema.sql exactly."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ── Tenancy ────────────────────────────────────────────────────────────────────

class Organization(Base):
    __tablename__ = "organizations"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:       Mapped[str]      = mapped_column(String(255), nullable=False)
    slug:       Mapped[str]      = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(String(32), default=lambda: datetime.utcnow().isoformat())

    users:     Mapped[list["User"]]     = relationship(back_populates="org", cascade="all, delete-orphan")
    customers: Mapped[list["Customer"]] = relationship(back_populates="org", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_org_user_email"),)

    id:            Mapped[str]      = mapped_column(String(36), primary_key=True)
    org_id:        Mapped[int]      = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email:         Mapped[str]      = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str]      = mapped_column(String(256), nullable=False)
    role:          Mapped[str]      = mapped_column(String(16), default="member", nullable=False)
    created_at:    Mapped[datetime] = mapped_column(String(32), default=lambda: datetime.utcnow().isoformat())

    org:            Mapped["Organization"]      = relationship(back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions:       Mapped[list["ChatSession"]]  = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    jti:        Mapped[str]  = mapped_column(String(36), primary_key=True)
    user_id:    Mapped[str]  = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at: Mapped[str]  = mapped_column(String(32), nullable=False)
    revoked:    Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[str]  = mapped_column(String(32), default=lambda: datetime.utcnow().isoformat())

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


# ── Chat sessions ──────────────────────────────────────────────────────────────

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id:   Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id:      Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id:       Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    context_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at:   Mapped[str] = mapped_column(String(32), default=lambda: datetime.utcnow().isoformat())
    last_active:  Mapped[str] = mapped_column(String(32), default=lambda: datetime.utcnow().isoformat())

    user:     Mapped["User"]               = relationship(back_populates="sessions")
    messages: Mapped[list["SessionMessage"]] = relationship(
        back_populates="session", order_by="SessionMessage.id", cascade="all, delete-orphan"
    )


class SessionMessage(Base):
    __tablename__ = "session_messages"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id:   Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at:   Mapped[str] = mapped_column(String(32), default=lambda: datetime.utcnow().isoformat())

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


# ── Shared customer identity ───────────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_org_customer_email"),)

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id:     Mapped[int]      = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name:       Mapped[str]      = mapped_column(String(255), nullable=False)
    email:      Mapped[str]      = mapped_column(String(254), nullable=False)
    created_at: Mapped[datetime] = mapped_column(String(32), default=lambda: datetime.utcnow().isoformat())

    org:            Mapped["Organization"]              = relationship(back_populates="customers")
    ecom_profile:   Mapped[Optional["EcomCustomerProfile"]]    = relationship(back_populates="customer", uselist=False, cascade="all, delete-orphan")
    support_profile: Mapped[Optional["SupportCustomerProfile"]] = relationship(back_populates="customer", uselist=False, cascade="all, delete-orphan")
    orders:  Mapped[list["EcomOrder"]]      = relationship(back_populates="customer", cascade="all, delete-orphan")
    tickets: Mapped[list["SupportTicket"]]  = relationship(back_populates="customer", cascade="all, delete-orphan")


class EcomCustomerProfile(Base):
    __tablename__ = "ecom_customer_profiles"

    customer_id: Mapped[int]            = mapped_column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True)
    location:    Mapped[Optional[str]]  = mapped_column(String(255), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="ecom_profile")


class SupportCustomerProfile(Base):
    __tablename__ = "support_customer_profiles"

    customer_id:    Mapped[int]           = mapped_column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True)
    contact_info:   Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_status: Mapped[str]           = mapped_column(String(32), default="active", nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="support_profile")


# ── Ecommerce domain ───────────────────────────────────────────────────────────

class EcomCategory(Base):
    __tablename__ = "ecom_categories"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id:      Mapped[int]           = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name:        Mapped[str]           = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    products: Mapped[list["EcomProduct"]] = relationship(back_populates="category")


class EcomProduct(Base):
    __tablename__ = "ecom_products"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id:      Mapped[int]           = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name:        Mapped[str]           = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price:       Mapped[float]         = mapped_column(Float, nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("ecom_categories.id", ondelete="SET NULL"), nullable=True)

    category: Mapped[Optional["EcomCategory"]] = relationship(back_populates="products")


class EcomOrder(Base):
    __tablename__ = "ecom_orders"

    id:           Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id:       Mapped[int]   = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id:  Mapped[int]   = mapped_column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    order_date:   Mapped[str]   = mapped_column(String(10), nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="orders")


# ── Support domain ─────────────────────────────────────────────────────────────

class SupportAgent(Base):
    __tablename__ = "support_agents"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id:     Mapped[int]           = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name:       Mapped[str]           = mapped_column(String(255), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expertise:  Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    interactions: Mapped[list["SupportInteraction"]] = relationship(back_populates="agent")


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id:      Mapped[int]           = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[int]           = mapped_column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    title:       Mapped[str]           = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status:      Mapped[str]           = mapped_column(String(20), default="open", nullable=False)
    priority:    Mapped[str]           = mapped_column(String(10), default="medium", nullable=False)
    created_at:  Mapped[str]           = mapped_column(String(32), default=lambda: datetime.utcnow().isoformat())

    customer:     Mapped["Customer"]                  = relationship(back_populates="tickets")
    interactions: Mapped[list["SupportInteraction"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")


class SupportInteraction(Base):
    __tablename__ = "support_interactions"

    id:        Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int]           = mapped_column(Integer, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id:  Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("support_agents.id", ondelete="SET NULL"), nullable=True)
    timestamp: Mapped[str]           = mapped_column(String(32), nullable=False)
    notes:     Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ticket: Mapped["SupportTicket"]        = relationship(back_populates="interactions")
    agent:  Mapped[Optional["SupportAgent"]] = relationship(back_populates="interactions")
