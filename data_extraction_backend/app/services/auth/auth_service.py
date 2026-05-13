"""Authentication service: register, login, token refresh, logout.

Design:
  - Access token (15 min) + Refresh token (7 days, persisted in DB)
  - Refresh token rotation: each /refresh call issues a fresh pair
  - org_id and role embedded in both tokens — no extra DB lookup per request
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.database import SessionLocal
from app.core.exceptions import AuthError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    revoke_refresh_token,
    verify_password,
)
from app.models.db import Organization, RefreshToken, User
from app.models.schemas import UserInfo

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower().strip()).strip("-") or "org"


class AuthService:

    def register(
        self, email: str, password: str, org_name: str
    ) -> tuple[UserInfo, str, str]:
        """Create org + admin user. Returns (user_info, access_token, refresh_token)."""
        email = email.lower().strip()

        with SessionLocal() as db:
            slug = _slugify(org_name)
            # Make slug unique if collision
            existing_slugs = {
                r[0] for r in db.execute(
                    select(Organization.slug).where(Organization.slug.like(f"{slug}%"))
                ).fetchall()
            }
            unique_slug = slug
            n = 1
            while unique_slug in existing_slugs:
                unique_slug = f"{slug}-{n}"
                n += 1

            org = Organization(name=org_name, slug=unique_slug)
            db.add(org)
            db.flush()  # get org.id

            # Reject duplicate email within this org (or globally for simplicity)
            if db.scalar(select(User).where(User.email == email)):
                raise ConflictError("An account with this email already exists.")

            user = User(
                id=str(uuid.uuid4()),
                org_id=org.id,
                email=email,
                password_hash=hash_password(password),
                role="admin",
            )
            db.add(user)
            db.flush()

            access_token = create_access_token(user.id, user.email, org.id, user.role)
            refresh_str, jti = create_refresh_token(user.id, user.email, org.id, user.role)
            expires_at = (
                datetime.now(tz=timezone.utc) + timedelta(days=7)
            ).isoformat()
            db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
            db.commit()

            info = UserInfo(
                user_id=user.id,
                email=user.email,
                org_id=org.id,
                org_name=org.name,
                role=user.role,
            )

        return info, access_token, refresh_str

    def login(self, email: str, password: str) -> tuple[UserInfo, str, str]:
        email = email.lower().strip()

        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            if user is None or not verify_password(password, user.password_hash):
                raise AuthError("Invalid email or password.")

            org = db.get(Organization, user.org_id)

            access_token = create_access_token(user.id, user.email, user.org_id, user.role)
            refresh_str, jti = create_refresh_token(user.id, user.email, user.org_id, user.role)
            expires_at = (
                datetime.now(tz=timezone.utc) + timedelta(days=7)
            ).isoformat()
            db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
            db.commit()

            info = UserInfo(
                user_id=user.id,
                email=user.email,
                org_id=user.org_id,
                org_name=org.name if org else "",
                role=user.role,
            )

        return info, access_token, refresh_str

    def refresh(self, refresh_token: str) -> tuple[UserInfo, str, str]:
        """Rotate token pair. Old refresh token is revoked atomically."""
        with SessionLocal() as db:
            payload = decode_refresh_token(refresh_token, db)

            # Revoke old token
            revoke_refresh_token(payload.jti, db)

            org = db.get(Organization, payload.org_id)
            new_access = create_access_token(
                payload.user_id, payload.email, payload.org_id, payload.role
            )
            new_refresh, new_jti = create_refresh_token(
                payload.user_id, payload.email, payload.org_id, payload.role
            )
            expires_at = (
                datetime.now(tz=timezone.utc) + timedelta(days=7)
            ).isoformat()
            db.add(RefreshToken(jti=new_jti, user_id=payload.user_id, expires_at=expires_at))
            db.commit()

            info = UserInfo(
                user_id=payload.user_id,
                email=payload.email,
                org_id=payload.org_id,
                org_name=org.name if org else "",
                role=payload.role,
            )

        return info, new_access, new_refresh

    def logout(self, refresh_token: str) -> None:
        with SessionLocal() as db:
            try:
                payload = decode_refresh_token(refresh_token, db)
                revoke_refresh_token(payload.jti, db)
                db.commit()
            except AuthError:
                pass  # already invalid — logout is idempotent
