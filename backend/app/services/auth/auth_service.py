"""JWT creation/verification and password hashing.

Design: pure service class with no framework coupling — unit-testable
without a running FastAPI app.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.chat import AuthResponse, UserPayload
from app.models.db import User

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ALGORITHM = "HS256"


class AuthService:
    def __init__(self) -> None:
        self._settings = get_settings()

    # ── Public API ─────────────────────────────────────────────────────────────

    def register(self, email: str, password: str) -> AuthResponse:
        email = email.lower().strip()
        with SessionLocal() as db:
            if db.query(User).filter_by(email=email).first():
                raise ValueError("An account with this email already exists.")
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=self._hash(password),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return AuthResponse(
            token=self._create_token(user.id, user.email),
            user_id=user.id,
            email=user.email,
        )

    def login(self, email: str, password: str) -> AuthResponse:
        email = email.lower().strip()
        with SessionLocal() as db:
            user = db.query(User).filter_by(email=email).first()
        if user is None or not self._verify(password, user.password_hash):
            raise ValueError("Invalid email or password.")
        return AuthResponse(
            token=self._create_token(user.id, user.email),
            user_id=user.id,
            email=user.email,
        )

    def decode_token(self, token: str) -> UserPayload:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[_ALGORITHM],
            )
        except JWTError as exc:
            raise ValueError("Invalid or expired token.") from exc
        return UserPayload(user_id=payload["sub"], email=payload["email"])

    # ── Private helpers ────────────────────────────────────────────────────────

    def _create_token(self, user_id: str, email: str) -> str:
        expire = datetime.now(tz=timezone.utc) + timedelta(
            days=self._settings.jwt_expire_days
        )
        return jwt.encode(
            {"sub": user_id, "email": email, "exp": expire},
            self._settings.jwt_secret,
            algorithm=_ALGORITHM,
        )

    @staticmethod
    def _hash(password: str) -> str:
        return _pwd_context.hash(password)

    @staticmethod
    def _verify(plain: str, hashed: str) -> bool:
        return _pwd_context.verify(plain, hashed)
