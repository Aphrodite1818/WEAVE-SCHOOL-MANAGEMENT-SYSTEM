# ==========================#
#   GEMINI PROVIDER.PY     #
# ==========================#


from typing import Any

from google import genai
from google.genai import types

from app.modules.AI.providers.base import BaseLLMProvider
from app.modules.AI.providers.utils import (
    model_to_dict,
    openai_tool_to_gemini_declaration,
    require_api_key,
    text_from_content,
)


class GeminiProvider(BaseLLMProvider):
    """Represent the GeminiProvider type."""

    def __init__(self, api_key: str | None, model: str, max_tokens: int):
        """Initialize the GeminiProvider instance."""
        self.api_key = require_api_key(api_key, "Gemini")
        self.model = model
        self.max_tokens = max_tokens
        self.client = genai.Client(api_key=self.api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Perform chat."""
        system_instruction = (
            "\n\n".join(
                text_from_content(message.get("content"))
                for message in messages
                if message.get("role") == "system"
            )
            or None
        )
        contents = [
            types.Content(
                role="model" if message.get("role") == "assistant" else "user",
                parts=[
                    types.Part.from_text(text=text_from_content(message.get("content")))
                ],
            )
            for message in messages
            if message.get("role") in {"user", "assistant"}
        ]

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": self.max_tokens,
        }

        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        if tools:
            config_kwargs["tools"] = [
                types.Tool(
                    function_declarations=[
                        openai_tool_to_gemini_declaration(tool) for tool in tools
                    ]
                )
            ]

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )

        return {
            "content": response.text or "",
            "tool_calls": model_to_dict(response.function_calls) or None,
            "raw_response": model_to_dict(response),
        }
