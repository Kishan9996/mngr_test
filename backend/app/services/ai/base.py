from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.chat import ProcessResult


class AIService(ABC):
    """Abstract AI service interface."""

    @abstractmethod
    def process_message(
        self, session_id: str, user_message: str, timezone: str
    ) -> ProcessResult:
        """Process a user message and return the assistant's reply with metadata."""
