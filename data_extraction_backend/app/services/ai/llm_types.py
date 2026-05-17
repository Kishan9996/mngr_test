"""Normalized LLM types shared by all provider implementations.

Design: Strategy + Factory
  BaseLLMProvider  — strategy interface; callers depend only on this.
  LLMResponse      — canonical response; providers convert from native format.
  ToolCall         — canonical tool invocation; replaces SDK-specific block types.
  LLMProviderFactory — creates the configured provider from Settings.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings


@dataclass
class ToolCall:
    """A single tool invocation from the model, in canonical form."""
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use"


class BaseLLMProvider(ABC):
    """Strategy interface for LLM backends.

    Messages use Anthropic canonical dict format for storage compatibility:
      {"role": "user",      "content": "text or list-of-blocks"}
      {"role": "assistant", "content": [{"type":"text","text":"..."},
                                        {"type":"tool_use","id":"...","name":"...","input":{}}]}
      {"role": "user",      "content": [{"type":"tool_result","tool_use_id":"...","content":"..."}]}

    Each provider converts to/from its own wire format internally.
    """

    @abstractmethod
    def chat(
        self,
        system: str | list[dict],
        tools: list[dict[str, Any]],
        messages: list[dict],
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send one conversation turn; return a normalized response."""


class LLMProviderFactory:
    """Reads `llm_provider` from Settings and returns the concrete strategy."""

    @staticmethod
    def create(settings: "Settings") -> BaseLLMProvider:
        provider = (settings.llm_provider or "claude").lower()

        if provider == "claude":
            from app.services.ai.providers.claude_provider import ClaudeProvider
            return ClaudeProvider(
                api_key=settings.anthropic_api_key,
                model=settings.claude_model,
            )

        if provider == "grok":
            from app.services.ai.providers.grok_provider import GrokProvider
            return GrokProvider(
                api_key=settings.grok_api_key,
                model=settings.grok_model,
            )

        raise ValueError(
            f"Unknown llm_provider '{provider}'. "
            "Set LLM_PROVIDER=claude or LLM_PROVIDER=grok in .env"
        )
