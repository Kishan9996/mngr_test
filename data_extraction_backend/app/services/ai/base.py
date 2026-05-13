from __future__ import annotations

from abc import ABC, abstractmethod


class AIService(ABC):

    @abstractmethod
    def process_message(self, session_id: str, user_message: str) -> str:
        """Process a user message and return the assistant reply."""
