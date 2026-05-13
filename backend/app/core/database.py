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
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables on startup (idempotent) and run lightweight column migrations."""
    import app.models.db  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate() -> None:
    """Add new columns to existing tables without a full migration framework."""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE user_profiles ADD COLUMN onboarding_completed BOOLEAN NOT NULL DEFAULT 0",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # Column already exists — safe to ignore
