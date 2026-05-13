"""JWT creation/verification and password hashing.

Two-token strategy:
  access  — 15 min, carries user identity + org context
  refresh — 7 days, stored in DB (jti column) for revocation
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthError

_ALGORITHM = "HS256"
_ACCESS_TYPE = "access"
_REFRESH_TYPE = "refresh"


# ── Token dataclass ────────────────────────────────────────────────────────────

class TokenPayload:
    __slots__ = ("user_id", "email", "org_id", "role", "token_type", "jti")

    def __init__(
        self,
        user_id: str,
        email: str,
        org_id: int,
        role: str,
        token_type: str,
        jti: Optional[str] = None,
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.org_id = org_id
        self.role = role
        self.token_type = token_type
        self.jti = jti


# ── Public API ─────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str, org_id: int, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(tz=timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "org_id": org_id,
            "role": role,
            "type": _ACCESS_TYPE,
            "exp": expire,
        },
        settings.jwt_secret,
        algorithm=_ALGORITHM,
    )


def create_refresh_token(user_id: str, email: str, org_id: int, role: str) -> tuple[str, str]:
    """Return (encoded_token, jti).  Caller must persist the jti in DB."""
    settings = get_settings()
    jti = str(uuid.uuid4())
    expire = datetime.now(tz=timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    token = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "org_id": org_id,
            "role": role,
            "type": _REFRESH_TYPE,
            "jti": jti,
            "exp": expire,
        },
        settings.jwt_secret,
        algorithm=_ALGORITHM,
    )
    return token, jti


def decode_access_token(token: str) -> TokenPayload:
    payload = _decode_raw(token)
    if payload.get("type") != _ACCESS_TYPE:
        raise AuthError("Invalid token type.")
    return _to_payload(payload)


def decode_refresh_token(token: str, db: Session) -> TokenPayload:
    """Decode and validate a refresh token — checks DB for revocation."""
    from app.models.db import RefreshToken

    payload = _decode_raw(token)
    if payload.get("type") != _REFRESH_TYPE:
        raise AuthError("Invalid token type.")

    jti = payload.get("jti")
    if not jti:
        raise AuthError("Malformed refresh token.")

    record = db.get(RefreshToken, jti)
    if record is None or record.revoked:
        raise AuthError("Refresh token has been revoked or does not exist.")

    return _to_payload(payload)


def revoke_refresh_token(jti: str, db: Session) -> None:
    from app.models.db import RefreshToken

    record = db.get(RefreshToken, jti)
    if record:
        record.revoked = True
        db.commit()


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Private ────────────────────────────────────────────────────────────────────

def _decode_raw(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise AuthError("Invalid or expired token.") from exc


def _to_payload(raw: dict) -> TokenPayload:
    return TokenPayload(
        user_id=raw["sub"],
        email=raw["email"],
        org_id=raw["org_id"],
        role=raw["role"],
        token_type=raw["type"],
        jti=raw.get("jti"),
    )
