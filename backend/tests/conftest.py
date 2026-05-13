"""Shared pytest fixtures.

Uses FastAPI dependency_overrides to:
  - Replace DBSessionStore with the in-memory SessionStore (no DB needed)
  - Inject a fake authenticated user so routes don't need real JWTs
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from unittest.mock import MagicMock

from app.api.deps import get_auth_service, get_current_user, get_session_store
from app.main import app
from app.models.appointment import CalendarTokens
from app.models.chat import UserPayload
from app.services.session.session_store import SessionStore

TEST_SESSION_ID = "test-session-00000000"
TEST_USER = UserPayload(user_id="test-user-id", email="test@example.com")

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
def override_dependencies():
    """Swap in fast, isolated in-memory dependencies for all tests."""
    # Fresh store per test
    store = SessionStore()
    store._sessions.clear()

    # Mock auth service: accepts any token → returns TEST_USER
    mock_auth = MagicMock()
    mock_auth.decode_token.return_value = TEST_USER

    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_auth_service] = lambda: mock_auth
    yield
    app.dependency_overrides.clear()
    store._sessions.clear()


@pytest.fixture
def store() -> SessionStore:
    """The same in-memory store used by overridden dependencies."""
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
