"""Integration tests for the chat and calendar HTTP endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import TEST_SESSION_ID


class TestChatEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @patch("app.api.routes.chat.get_ai_service")
    def test_send_message_returns_response(self, mock_get_ai, client, store):
        mock_ai = MagicMock()
        mock_ai.process_message.return_value = "Hello! I'm your scheduling assistant."
        mock_get_ai.return_value = mock_ai

        response = client.post(
            "/api/chat/message",
            json={
                "session_id": TEST_SESSION_ID,
                "message": "Hi",
                "timezone": "UTC",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == TEST_SESSION_ID
        assert "response" in data
        assert "connected_providers" in data

    def test_send_message_rejects_empty_message(self, client):
        response = client.post(
            "/api/chat/message",
            json={
                "session_id": TEST_SESSION_ID,
                "message": "",
                "timezone": "UTC",
            },
        )
        assert response.status_code == 422

    def test_get_status_returns_connected_providers(
        self, client, session_with_google
    ):
        response = client.get(
            "/api/chat/status", params={"session_id": session_with_google}
        )
        assert response.status_code == 200
        data = response.json()
        assert "google" in data["connected_providers"]

    def test_get_status_empty_for_new_session(self, client):
        response = client.get(
            "/api/chat/status", params={"session_id": "brand-new-session"}
        )
        assert response.status_code == 200
        assert response.json()["connected_providers"] == []


class TestCalendarEndpoints:
    def test_list_providers(self, client):
        response = client.get("/api/calendar/providers")
        assert response.status_code == 200
        data = response.json()
        assert "google" in data["providers"]
        assert "outlook" in data["providers"]

    def test_start_oauth_unknown_provider(self, client):
        response = client.get(
            "/api/calendar/auth/unknown",
            params={"session_id": TEST_SESSION_ID},
            follow_redirects=False,
        )
        assert response.status_code == 400

    @patch("app.api.routes.calendar.CalendarProviderFactory.create_unauthenticated")
    def test_start_oauth_google_redirects(self, mock_factory, client):
        mock_provider = MagicMock()
        mock_provider.get_auth_url.return_value = "https://accounts.google.com/oauth?state=test"
        mock_factory.return_value = mock_provider

        response = client.get(
            "/api/calendar/auth/google",
            params={"session_id": TEST_SESSION_ID},
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)

    def test_disconnect_calendar(self, client, session_with_google):
        response = client.delete(
            "/api/calendar/disconnect/google",
            params={"session_id": session_with_google},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch("app.api.routes.calendar.CalendarProviderFactory.create_unauthenticated")
    def test_oauth_callback_stores_tokens(self, mock_factory, client, store):
        from app.models.appointment import CalendarTokens

        mock_provider = MagicMock()
        mock_provider.exchange_code.return_value = CalendarTokens(
            provider="google", access_token="new-token"
        )
        mock_factory.return_value = mock_provider

        response = client.get(
            "/api/calendar/auth/google/callback",
            params={"code": "auth-code-123", "state": TEST_SESSION_ID},
            follow_redirects=False,
        )
        # Should redirect to frontend
        assert response.status_code in (302, 307)
        tokens = store.get_tokens(TEST_SESSION_ID, "google")
        assert tokens is not None
        assert tokens.access_token == "new-token"


class TestSessionStore:
    def test_get_or_create_new_session(self, store):
        session = store.get_or_create("fresh-session")
        assert session.session_id == "fresh-session"
        assert session.conversation_history == []
        assert session.calendar_tokens == {}

    def test_save_and_retrieve_tokens(self, store):
        from app.models.appointment import CalendarTokens

        tokens = CalendarTokens(provider="google", access_token="tok")
        store.save_tokens("s1", tokens)
        retrieved = store.get_tokens("s1", "google")
        assert retrieved.access_token == "tok"

    def test_remove_tokens(self, store):
        from app.models.appointment import CalendarTokens

        store.save_tokens("s2", CalendarTokens(provider="google", access_token="t"))
        store.remove_tokens("s2", "google")
        assert store.get_tokens("s2", "google") is None

    def test_connected_providers(self, store):
        from app.models.appointment import CalendarTokens

        store.save_tokens("s3", CalendarTokens(provider="google", access_token="g"))
        store.save_tokens("s3", CalendarTokens(provider="outlook", access_token="o"))
        providers = store.connected_providers("s3")
        assert set(providers) == {"google", "outlook"}
