from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_auth_service, get_current_user
from app.models.chat import AuthResponse, LoginRequest, RegisterRequest, UserPayload
from app.services.auth.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(
    body: RegisterRequest,
    auth: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        return auth.register(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        return auth.login(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.get("/me", response_model=UserPayload)
def me(current_user: UserPayload = Depends(get_current_user)) -> UserPayload:
    return current_user
