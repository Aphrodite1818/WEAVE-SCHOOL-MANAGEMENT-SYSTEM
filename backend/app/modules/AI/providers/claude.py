# ==========================#
#     CLAUDE PROVIDER.PY   #
# ==========================#

from typing import Any

import httpx

from app.modules.AI.providers.base import BaseLLMProvider
from app.modules.AI.providers.utils import (
    openai_tool_to_anthropic,
    require_api_key,
    text_from_content,
)


class ClaudeProvider(BaseLLMProvider):
    """Represent the ClaudeProvider type."""

    def __init__(self, api_key: str | None, model: str, max_tokens: int) -> None:
        """Initialize the ClaudeProvider instance."""
        self.api_key = require_api_key(api_key, "Anthropic")
        self.model = model
        self.max_tokens = max_tokens

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Perform chat."""
        system_messages = [
            text_from_content(message.get("content"))
            for message in messages
            if message.get("role") == "system"
        ]
        claude_messages = [
            message for message in messages if message.get("role") in {"user", "assistant"}
        ]

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": claude_messages,
        }

        if system_messages:
            payload["system"] = "\n\n".join(system_messages)

        if tools:
            payload["tools"] = [openai_tool_to_anthropic(tool) for tool in tools]

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

        raw_response = response.json()
        content_blocks = raw_response.get("content", [])
        text_blocks = [
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        ]
        tool_calls = [block for block in content_blocks if block.get("type") == "tool_use"]

        return {
            "content": "\n".join(text_blocks),
            "tool_calls": tool_calls or None,
            "raw_response": raw_response,
        }
