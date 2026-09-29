"""Gemini provider implementations for CBT AI question writing"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import httpx
from pydantic import SecretStr

from app.config.settings import settings
from app.modules.cbt.ai.providers.base import (
    BaseImageGenerationProvider,
    BaseQuestionGenerationProvider,
    ProviderGeneratedImage,
    ProviderImageGenerationResult,
    ProviderQuestionGenerationResult,
    ProviderQuestionRegenerationResult,
    ProviderUsage,
)


# Exceptions
class GeminiProviderError(RuntimeError):
    """Raised when Gemini cannot successfully complete a provider request"""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiProviderNotConfiguredError(GeminiProviderError):
    """Raised when Gemini is invoked without an API Key"""


class _GeminiHTTPProvider:
    """
    Shared REST behaviour for Gemini-backed CBT AI Providers.
    This class is internal and should not be used directly
    """

    provider_name = "gemini"

    def __init__(self, *, api_key: SecretStr | str | None = None, base_url: str | None = None):
        configured_api_key = api_key if api_key is not None else settings.GEMINI_API_KEY

        if isinstance(configured_api_key, SecretStr):
            configured_api_key = configured_api_key.get_secret_value()

        self.api_key = configured_api_key.strip() if configured_api_key else None

        self.base_url = (base_url or settings.GEMINI_BASE_URL).rstrip("/")

    def is_configured(self) -> bool:
        """Return whether Gemini has the credentials required to operate"""
        return bool(self.api_key)

    def _require_api_key(self) -> str:
        """
        Return the configured API Key

        Gemini credentials are intentionally optional during application
        startup. Failure happens only when Gemini is actually invoked
        """

        if not self.api_key:
            raise GeminiProviderNotConfiguredError("Gemini CBT AI provider is not configured")

        return self.api_key

    def _build_url(self, model: str) -> str:
        """Build the Gemini generateContent endpoint for a model"""

        return f"{self.base_url}/models/{model}:generateContent"

    async def _post(self, *, model: str, payload: dict[str, Any], timeout: float):
        """Execute a Gemini REST request and return  the decoded response"""

        api_key = self._require_api_key()

        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self._build_url(model), headers=headers, json=payload)

        except httpx.TimeoutException as exc:
            raise GeminiProviderError("Gemini request timed out") from exc

        except httpx.RequestError as exc:
            raise GeminiProviderError("Unable to connect to Gemini") from exc

        if response.is_error:
            raise GeminiProviderError(
                self._extract_error_message(response), status_code=response.status_code
            )

        try:
            data = response.json()

        except ValueError as exc:
            raise GeminiProviderError("Gemini returned an invalid JSON response") from exc

        if not isinstance(data, dict):
            raise GeminiProviderError("Gemini returned an unexpected response structure")
        return data

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Report HTTP failure without exposing upstream credentials or content."""
        return f"Gemini request failed with HTTP {response.status_code}"

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
        """Extract text returned by Gemini from the first candidate."""

        candidates = response.get("candidates")

        if not isinstance(candidates, list) or not candidates:
            raise GeminiProviderError("Gemini returned no candidates.")

        candidate = candidates[0]

        if not isinstance(candidate, dict):
            raise GeminiProviderError("Gemini returned an invalid candidate.")

        content = candidate.get("content")

        if not isinstance(content, dict):
            raise GeminiProviderError("Gemini candidate contains no content.")

        parts = content.get("parts")

        if not isinstance(parts, list) or not parts:
            raise GeminiProviderError("Gemini candidate contains no content parts.")

        text_parts: list[str] = []

        for part in parts:
            if not isinstance(part, dict) or part.get("thought"):
                continue

            text = part.get("text")

            if isinstance(text, str) and text.strip():
                text_parts.append(text)

        if not text_parts:
            raise GeminiProviderError("Gemini returned no text content.")

        return "".join(text_parts).strip()

    @staticmethod
    def _parse_json_text(text: str) -> dict[str, Any]:
        """Parse structured JSON text returned by Gemini."""

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiProviderError("Gemini returned malformed structured JSON.") from exc

        if not isinstance(parsed, dict):
            raise GeminiProviderError("Gemini structured output must be a JSON object.")

        return parsed

    @staticmethod
    def _extract_usage(response: dict[str, Any]) -> ProviderUsage:
        """Normalize token counts, including reasoning and cached input tokens."""
        usage = response.get("usageMetadata")
        if not isinstance(usage, dict):
            return ProviderUsage()

        def token_count(key: str) -> int:
            value = usage.get(key, 0)
            return value if type(value) is int and value >= 0 else 0

        return ProviderUsage(
            input_tokens=token_count("promptTokenCount"),
            output_tokens=token_count("candidatesTokenCount") + token_count("thoughtsTokenCount"),
            cache_read_tokens=token_count("cachedContentTokenCount"),
        )


# QUESTION GENERATION


class GeminiQuestionGenerationProvider(_GeminiHTTPProvider, BaseQuestionGenerationProvider):
    """Generate and regenerate CBT question drafts using Gemini"""

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_output_tokens: int | None = None,
        timeout: float | None = None,
    ):
        super().__init__(api_key=api_key, base_url=base_url)

        self.model = model or settings.GEMINI_TEXT_MODEL

        self.max_output_tokens = max_output_tokens or settings.GEMINI_MAX_OUTPUT_TOKENS

        self.timeout = timeout or settings.GEMINI_REQUEST_TIMEOUT_SECONDS

    async def generate_questions(
        self,
        *,
        request: Mapping[str, Any],
    ) -> ProviderQuestionGenerationResult:
        """Generate a batch of CBT question drafts"""
        request_payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are a CBT educational question "
                            "authoring engine. Generate questions "
                            "strictly from the supplied academic "
                            "context and author instructions. "
                            "Return only valid JSON. "
                            "The top-level JSON object must contain "
                            "a 'questions' array. Do not wrap the "
                            "response in markdown or code fences"
                        )
                    }
                ]
            },
            "contents": [
                {"role": "user", "parts": [{"text": json.dumps(dict(request), ensure_ascii=False)}]}
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": self.max_output_tokens,
            },
        }

        response = await self._post(model=self.model, payload=request_payload, timeout=self.timeout)

        text = self._extract_text(response)
        result = self._parse_json_text(text)

        questions = result.get("questions")

        if not isinstance(questions, list) or any(not isinstance(q, dict) for q in questions):
            raise GeminiProviderError(
                "Gemini question-generation response does not "
                "contain a valid 'questions' array of objects."
            )

        return ProviderQuestionGenerationResult(
            questions=questions, usage=self._extract_usage(response), raw_response=response
        )

    async def regenerate_question(
        self,
        *,
        request: Mapping[str, Any],
    ) -> ProviderQuestionRegenerationResult:
        """Regenerate or transform one existing CBT question draft."""

        request_payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are a CBT educational question "
                            "editing engine. Transform exactly one "
                            "existing question using the supplied "
                            "academic context and transformation "
                            "instruction. Preserve constraints such "
                            "as subject, level, topic and question "
                            "type unless the request explicitly "
                            "allows a change. Return only valid JSON. "
                            "The top-level JSON object must contain "
                            "a 'question' object. Do not use markdown "
                            "or code fences."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                dict(request),
                                ensure_ascii=False,
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": self.max_output_tokens,
            },
        }

        response = await self._post(
            model=self.model,
            payload=request_payload,
            timeout=self.timeout,
        )

        text = self._extract_text(response)
        result = self._parse_json_text(text)

        question = result.get("question")

        if not isinstance(question, dict):
            raise GeminiProviderError(
                "Gemini regeneration response does not contain a valid 'question' object."
            )

        return ProviderQuestionRegenerationResult(
            question=question, usage=self._extract_usage(response), raw_response=response
        )


# IMAGE GENERATION


class GeminiImageGenerationProvider(_GeminiHTTPProvider, BaseImageGenerationProvider):
    """Generate CBT visual assets using Gemini's image model"""

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        super().__init__(api_key=api_key, base_url=base_url)

        self.model = model or settings.GEMINI_IMAGE_MODEL

        self.timeout = timeout or settings.GEMINI_IMAGE_TIMEOUT_SECONDS

    async def generate_image(
        self,
        *,
        prompt: str,
        metadata: Mapping[str, Any] | None = None,
        reference_images: Sequence[str] | None = None,
    ) -> ProviderImageGenerationResult:
        """Generate a single image from a CBT visual prompt."""

        normalized_prompt = prompt.strip()

        if not normalized_prompt:
            raise ValueError("Image generation prompt cannot be empty.")

        if reference_images:
            raise ValueError("Reference images are not supported by this provider yet.")
        if metadata:
            normalized_prompt += "\nImage context: " + json.dumps(
                dict(metadata), ensure_ascii=False
            )

        request_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": normalized_prompt,
                        }
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": [
                    "IMAGE",
                ],
            },
        }

        response = await self._post(
            model=self.model,
            payload=request_payload,
            timeout=self.timeout,
        )

        image = self._extract_image(response)

        return ProviderImageGenerationResult(
            image=ProviderGeneratedImage(
                content_type=image["mime_type"], data_base64=image["data_base64"]
            ),
            usage=self._extract_usage(response),
            raw_response=response,
        )

    @staticmethod
    def _extract_image(
        response: dict[str, Any],
    ) -> dict[str, str]:
        """Extract the first generated image returned by Gemini."""

        candidates = response.get("candidates")

        if not isinstance(candidates, list) or not candidates:
            raise GeminiProviderError("Gemini returned no image candidates.")

        candidate = candidates[0]

        if not isinstance(candidate, dict):
            raise GeminiProviderError("Gemini returned an invalid image candidate.")

        content = candidate.get("content")

        if not isinstance(content, dict):
            raise GeminiProviderError("Gemini image candidate contains no content.")

        parts = content.get("parts")

        if not isinstance(parts, list):
            raise GeminiProviderError("Gemini image candidate contains no parts.")

        for part in parts:
            if not isinstance(part, dict) or part.get("thought"):
                continue

            inline_data = part.get("inlineData")

            if not isinstance(inline_data, dict):
                continue

            mime_type = inline_data.get("mimeType")
            data = inline_data.get("data")

            if (
                isinstance(mime_type, str)
                and mime_type.startswith("image/")
                and isinstance(data, str)
                and data
            ):
                return {
                    "mime_type": mime_type,
                    "data_base64": data,
                }

        raise GeminiProviderError("Gemini returned no generated image data.")
