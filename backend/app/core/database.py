"""SQLAlchemy engine, session factory, and declarative Base.

Using synchronous SQLite for simplicity; swap DATABASE_URL in .env
for PostgreSQL in production without changing any other file.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False},  # needed for SQLite
    echo=_settings.app_env == "development",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables on startup (idempotent)."""
    # Import models so Base knows about them before create_all
    import app.models.db  # noqa: F401
    Base.metadata.create_all(bind=engine)
