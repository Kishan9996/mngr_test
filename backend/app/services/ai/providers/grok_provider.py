"""xAI Grok provider — concrete LLM strategy via OpenAI-compatible API.

Wire format differences handled here so the rest of the codebase never
knows which provider is active:

  Tool schema:  Anthropic  input_schema  →  OpenAI  parameters
  Messages:     Anthropic canonical dicts  →  OpenAI role/content/tool_calls
  Tool results: user message with list[tool_result]  →  role=tool messages
  Response:     OpenAI choice  →  LLMResponse
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.services.ai.llm_types import BaseLLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

_GROK_BASE_URL = "https://api.x.ai/v1"


class GrokProvider(BaseLLMProvider):
    """Sends canonical messages to xAI Grok; returns a normalized LLMResponse."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key, base_url=_GROK_BASE_URL)
        self._model = model

    def chat(
        self,
        system: str | list[dict],
        tools: list[dict[str, Any]],
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> LLMResponse:
        oai_messages = [{"role": "system", "content": _system_to_str(system)}]
        oai_messages.extend(_to_openai_messages(messages))

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": oai_messages,
        }
        if tools:
            kwargs["tools"] = [_to_openai_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        text = msg.content or ""
        tool_calls: list[ToolCall] = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, input=args)
                )

        stop_reason = "tool_use" if choice.finish_reason == "tool_calls" else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop_reason)


# ── Format converters ──────────────────────────────────────────────────────────

def _system_to_str(system: str | list[dict]) -> str:
    """Flatten multi-block system prompt to plain text (drops cache_control)."""
    if isinstance(system, str):
        return system
    return "\n\n".join(
        block.get("text", "") for block in system if isinstance(block, dict)
    )


def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert Anthropic tool definition to OpenAI function format."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


def _to_openai_messages(messages: list[dict]) -> list[dict]:
    """Convert canonical Anthropic-format message history to OpenAI format.

    Canonical user messages with tool_result blocks become role=tool messages.
    Canonical assistant messages with tool_use blocks become role=assistant
    with tool_calls[].
    """
    result: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content")

        if role == "user":
            if isinstance(content, str):
                result.append({"role": "user", "content": content})
            elif isinstance(content, list):
                tool_results = [
                    b for b in content
                    if isinstance(b, dict) and b.get("type") == "tool_result"
                ]
                text_blocks = [
                    b for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                # Emit one role=tool message per result
                for tr in tool_results:
                    result.append({
                        "role": "tool",
                        "tool_call_id": tr.get("tool_use_id", ""),
                        "content": tr.get("content", ""),
                    })
                if text_blocks:
                    text = " ".join(b.get("text", "") for b in text_blocks)
                    result.append({"role": "user", "content": text})

        elif role == "assistant":
            if isinstance(content, str):
                result.append({"role": "assistant", "content": content})
            elif isinstance(content, list):
                text = ""
                tool_calls: list[dict] = []
                for block in content:
                    b = block if isinstance(block, dict) else _block_to_dict(block)
                    if b.get("type") == "text":
                        text += b.get("text", "")
                    elif b.get("type") == "tool_use":
                        tool_calls.append({
                            "id": b["id"],
                            "type": "function",
                            "function": {
                                "name": b["name"],
                                "arguments": json.dumps(b.get("input", {})),
                            },
                        })
                msg_out: dict[str, Any] = {"role": "assistant", "content": text or None}
                if tool_calls:
                    msg_out["tool_calls"] = tool_calls
                result.append(msg_out)

    return result


def _block_to_dict(block: Any) -> dict:
    """Coerce an Anthropic SDK content block to a plain dict (fallback path)."""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    return {"type": getattr(block, "type", "text"), "text": str(block)}
