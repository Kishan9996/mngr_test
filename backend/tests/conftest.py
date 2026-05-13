"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.appointment import CalendarTokens
from app.services.session.session_store import SessionStore

TEST_SESSION_ID = "test-session-00000000"
GOOGLE_TOKENS = CalendarTokens(
    provider="google",
    access_token="fake-access-token",
    refresh_token="fake-refresh-token",
    extra={"token_uri": "https://oauth2.googleapis.com/token"},
)
OUTLOOK_TOKENS = CalendarTokens(
    provider="outlook",
    access_token="fake-outlook-token",
    refresh_token="fake-outlook-refresh",
)


@pytest.fixture(autouse=True)
def reset_session_store():
    """Reset singleton session store between tests."""
    store = SessionStore()
    store._sessions.clear()
    yield
    store._sessions.clear()


@pytest.fixture
def store() -> SessionStore:
    return SessionStore()


@pytest.fixture
def session_with_google(store: SessionStore) -> str:
    store.save_tokens(TEST_SESSION_ID, GOOGLE_TOKENS)
    return TEST_SESSION_ID


@pytest.fixture
def session_with_outlook(store: SessionStore) -> str:
    store.save_tokens(TEST_SESSION_ID, OUTLOOK_TOKENS)
    return TEST_SESSION_ID


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
