"""User profile service — manages working hours and scheduling preferences."""

from __future__ import annotations

import logging
from datetime import datetime

from app.core.database import SessionLocal
from app.models.chat import UserProfileResponse, UserProfileUpdate
from app.models.db import UserProfile

logger = logging.getLogger(__name__)

_DEFAULTS = dict(
    work_start="09:00",
    work_end="17:00",
    default_duration_minutes=60,
    timezone="UTC",
)


class ProfileService:
    def get_or_create(self, user_id: str) -> UserProfileResponse:
        with SessionLocal() as db:
            profile = db.get(UserProfile, user_id)
            if profile is None:
                profile = UserProfile(user_id=user_id, **_DEFAULTS)
                db.add(profile)
                db.commit()
                db.refresh(profile)
            return self._to_response(profile)

    def update(self, user_id: str, patch: UserProfileUpdate) -> UserProfileResponse:
        with SessionLocal() as db:
            profile = db.get(UserProfile, user_id)
            if profile is None:
                data = {**_DEFAULTS, **patch.model_dump(exclude_none=True)}
                profile = UserProfile(user_id=user_id, **data)
                db.add(profile)
            else:
                for field, value in patch.model_dump(exclude_none=True).items():
                    setattr(profile, field, value)
                profile.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(profile)
            logger.info("Profile updated for user %s", user_id)
            return self._to_response(profile)

    @staticmethod
    def _to_response(profile: UserProfile) -> UserProfileResponse:
        return UserProfileResponse(
            work_start=profile.work_start,
            work_end=profile.work_end,
            default_duration_minutes=profile.default_duration_minutes,
            timezone=profile.timezone,
        )
