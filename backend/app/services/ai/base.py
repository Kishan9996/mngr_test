from __future__ import annotations

from abc import ABC, abstractmethod


class AIService(ABC):
    """Abstract AI service interface."""

    @abstractmethod
    def process_message(self, session_id: str, user_message: str, timezone: str) -> str:
        """Process a user message and return the assistant's text reply."""
