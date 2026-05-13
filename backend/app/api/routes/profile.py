from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_profile_service
from app.models.chat import UserPayload, UserProfileResponse, UserProfileUpdate
from app.services.profile.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=UserProfileResponse)
def get_profile(
    current_user: UserPayload = Depends(get_current_user),
    profile_svc: ProfileService = Depends(get_profile_service),
) -> UserProfileResponse:
    """Return the current user's scheduling preferences (creates defaults if none set)."""
    return profile_svc.get_or_create(current_user.user_id)


@router.patch("", response_model=UserProfileResponse)
def update_profile(
    body: UserProfileUpdate,
    current_user: UserPayload = Depends(get_current_user),
    profile_svc: ProfileService = Depends(get_profile_service),
) -> UserProfileResponse:
    """Update one or more scheduling preference fields (partial update)."""
    return profile_svc.update(current_user.user_id, body)
