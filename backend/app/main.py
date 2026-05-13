"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import auth, calendar, chat, profile
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialised")
    yield


app = FastAPI(
    title="AI Calendar Scheduling Assistant",
    description="Conversational AI chatbot for scheduling via Google Calendar & Outlook.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware (outermost first) ───────────────────────────────────────────────
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(calendar.router, prefix="/api")
app.include_router(profile.router, prefix="/api")

# ── User-friendly error messages ──────────────────────────────────────────────
_SAFE_MESSAGES: dict[str, str] = {
    "CalendarAuthError":      "Your calendar connection needs to be renewed. Please reconnect from the sidebar.",
    "CalendarAPIError":       "Unable to reach the calendar service. Please try again shortly.",
    "AIServiceError":         "The AI service is temporarily unavailable. Please try again.",
    "SlotNotAvailableError":  "That time slot is no longer available. Please choose another.",
    "PastBookingError":       "That time has already passed. Please choose a future date and time.",
    "SessionNotFoundError":   "Your session has expired. Please refresh the page.",
    "UnsupportedProviderError": "This calendar provider is not supported.",
}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    rid = getattr(request.state, "request_id", "-")
    safe = _SAFE_MESSAGES.get(type(exc).__name__, exc.message)
    logger.warning("AppError [%s] rid=%s: %s", exc.status_code, rid, exc.message)
    return JSONResponse(status_code=exc.status_code, content={"detail": safe, "request_id": rid})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = getattr(request.state, "request_id", "-")
    logger.exception("Unhandled exception rid=%s", rid)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again.", "request_id": rid},
    )


# ── Health / root ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health() -> dict:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
        logger.error("Health check: DB unreachable")

    status = "ok" if db_ok else "degraded"
    return {"status": status, "db": "ok" if db_ok else "error", "service": "ai-calendar-chatbot"}


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"message": "AI Calendar Scheduling Assistant API", "docs": "/docs"}
