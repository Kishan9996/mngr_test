"""Anthropic Claude provider — concrete LLM strategy."""

from __future__ import annotations

from typing import Any

import anthropic

from app.services.ai.llm_types import BaseLLMProvider, LLMResponse, ToolCall


class ClaudeProvider(BaseLLMProvider):
    """Sends canonical messages to Anthropic; returns a normalized LLMResponse.

    The Anthropic SDK accepts plain dicts in messages[], so canonical stored
    format passes through without conversion.  cache_control blocks in the
    system prompt are forwarded as-is, preserving prompt caching.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def chat(
        self,
        system: str | list[dict],
        tools: list[dict[str, Any]],
        messages: list[dict],
        max_tokens: int = 1024,
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )

        text = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if hasattr(block, "type"):
                if block.type == "text":
                    text = block.text
                elif block.type == "tool_use":
                    tool_calls.append(
                        ToolCall(id=block.id, name=block.name, input=block.input)
                    )

        stop_reason = "tool_use" if response.stop_reason == "tool_use" else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop_reason)
