# ==========================#
#    OPENAI PROVIDER.PY    #
# ==========================#


from typing import Any

import httpx

from app.modules.AI.providers.base import BaseLLMProvider
from app.modules.AI.providers.utils import require_api_key


class OpenAIProvider(BaseLLMProvider):
    """Represent the OpenAIProvider type."""

    def __init__(self, api_key: str | None, model: str, max_tokens: int):
        """Initialize the OpenAIProvider instance."""
        self.api_key = require_api_key(api_key, "OpenAI")
        self.model = model
        self.max_tokens = max_tokens

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Perform chat."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

        raw_response = response.json()
        message = raw_response["choices"][0]["message"]

        return {
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls"),
            "raw_response": raw_response,
        }
