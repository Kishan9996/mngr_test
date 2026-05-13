from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import SessionLocal

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "service": "ai-data-extraction-chatbot",
    }
