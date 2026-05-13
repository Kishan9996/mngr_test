from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from app.api.deps import get_auth_service, get_current_user, get_session_store
from app.core.limiter import limit_auth_login, limit_auth_register
from app.models.chat import LoginRequest, RegisterRequest, UserPayload
from app.services.auth.auth_service import AuthService
from app.services.session.abstract_store import AbstractSessionStore

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

_REGISTER_RATE = Depends(limit_auth_register)
_LOGIN_RATE = Depends(limit_auth_login)

_COOKIE = "auth_token"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _set_auth_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key=_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
        # secure=True,  # uncomment when serving over HTTPS
    )


@router.post("/register", status_code=201, dependencies=[_REGISTER_RATE])
def register(
    request: Request,
    body: RegisterRequest,
    auth: AuthService = Depends(get_auth_service),
    store: AbstractSessionStore = Depends(get_session_store),
) -> JSONResponse:
    try:
        result = auth.register(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    session_id = store.get_or_create_for_user(result.user_id)
    payload = {"user_id": result.user_id, "email": result.email, "session_id": session_id}
    response = JSONResponse(content=payload, status_code=201)
    _set_auth_cookie(response, result.token)
    return response


@router.post("/login", dependencies=[_LOGIN_RATE])
def login(
    request: Request,
    body: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
    store: AbstractSessionStore = Depends(get_session_store),
) -> JSONResponse:
    try:
        result = auth.login(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    session_id = store.get_or_create_for_user(result.user_id)
    payload = {"user_id": result.user_id, "email": result.email, "session_id": session_id}
    response = JSONResponse(content=payload)
    _set_auth_cookie(response, result.token)
    return response


@router.post("/logout")
def logout() -> JSONResponse:
    response = JSONResponse(content={"success": True})
    response.delete_cookie(_COOKIE, path="/", samesite="lax")
    return response


@router.get("/me")
def me(
    current_user: UserPayload = Depends(get_current_user),
    store: AbstractSessionStore = Depends(get_session_store),
) -> JSONResponse:
    session_id = store.get_or_create_for_user(current_user.user_id)
    return JSONResponse({
        "user_id": current_user.user_id,
        "email": current_user.email,
        "session_id": session_id,
    })
