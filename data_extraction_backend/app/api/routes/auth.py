"""Auth routes: register, login, refresh, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, Request

from app.api.deps import get_auth_service, get_current_user, _REFRESH_COOKIE, _ACCESS_COOKIE
from app.core.exceptions import AuthError, ConflictError
from app.models.schemas import LoginRequest, RegisterRequest, UserInfo
from app.services.auth.auth_service import AuthService
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()
_SECURE = _settings.app_env == "production"
_SAMESITE = "lax"


def _set_tokens(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        key=_ACCESS_COOKIE,
        value=access,
        httponly=True,
        secure=_SECURE,
        samesite=_SAMESITE,
        max_age=_settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh,
        httponly=True,
        secure=_SECURE,
        samesite=_SAMESITE,
        path="/api/auth/refresh",
        max_age=_settings.refresh_token_expire_days * 86400,
    )


def _clear_tokens(response: Response) -> None:
    response.delete_cookie(_ACCESS_COOKIE)
    response.delete_cookie(_REFRESH_COOKIE, path="/api/auth/refresh")


@router.post("/register", response_model=UserInfo)
def register(
    body: RegisterRequest,
    response: Response,
    svc: AuthService = Depends(get_auth_service),
) -> UserInfo:
    try:
        info, access, refresh = svc.register(body.email, body.password, body.org_name)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.message)
    _set_tokens(response, access, refresh)
    return info


@router.post("/login", response_model=UserInfo)
def login(
    body: LoginRequest,
    response: Response,
    svc: AuthService = Depends(get_auth_service),
) -> UserInfo:
    try:
        info, access, refresh = svc.login(body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=exc.message)
    _set_tokens(response, access, refresh)
    return info


@router.post("/refresh", response_model=UserInfo)
def refresh_tokens(
    request: Request,
    response: Response,
    svc: AuthService = Depends(get_auth_service),
) -> UserInfo:
    token = request.cookies.get(_REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token.")
    try:
        info, access, refresh = svc.refresh(token)
    except AuthError as exc:
        _clear_tokens(response)
        raise HTTPException(status_code=401, detail=exc.message)
    _set_tokens(response, access, refresh)
    return info


@router.post("/logout", status_code=204, response_model=None)
def logout(
    request: Request,
    response: Response,
    svc: AuthService = Depends(get_auth_service),
) -> None:
    token = request.cookies.get(_REFRESH_COOKIE)
    if token:
        svc.logout(token)
    _clear_tokens(response)


@router.get("/me", response_model=UserInfo)
def me(
    request: Request,
    payload=Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
) -> UserInfo:
    from app.core.database import SessionLocal
    from sqlalchemy import select
    from app.models.db import Organization, User

    with SessionLocal() as db:
        user = db.get(User, payload.user_id)
        org  = db.get(Organization, payload.org_id) if user else None

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    return UserInfo(
        user_id=user.id,
        email=user.email,
        org_id=user.org_id,
        org_name=org.name if org else "",
        role=user.role,
    )
