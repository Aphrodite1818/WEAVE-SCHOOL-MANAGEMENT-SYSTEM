"""Gemini provider implementations for CBT AI question writing."""

from __future__ import annotations

import base64
import json
from typing import Any, Mapping, Sequence

import httpx
from pydantic import SecretStr

from app.config.settings import settings
from app.modules.cbt.ai.providers.base import (
    BaseImageEvaluationProvider,
    BaseImageGenerationProvider,
    BaseQuestionGenerationProvider,
    ImageCandidate,
    ProviderGeneratedImage,
    ProviderImageEvaluationResult,
    ProviderImageGenerationResult,
    ProviderQuestionGenerationResult,
    ProviderQuestionRegenerationResult,
    ProviderUsage,
)


# Exceptions
class GeminiProviderError(RuntimeError):
    """Raised when Gemini cannot successfully complete a provider request."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiProviderNotConfiguredError(GeminiProviderError):
    """Raised when Gemini is invoked without an API key."""


class _GeminiHTTPProvider:
    """
    Shared REST behaviour for Gemini-backed CBT AI providers.

    This class is internal and should not be used directly.
    """

    provider_name = "gemini"

    def __init__(self, *, api_key: SecretStr | str | None = None, base_url: str | None = None):
        configured_api_key = api_key if api_key is not None else settings.GEMINI_API_KEY

        if isinstance(configured_api_key, SecretStr):
            configured_api_key = configured_api_key.get_secret_value()

        self.api_key = configured_api_key.strip() if configured_api_key else None
        self.base_url = (base_url or settings.GEMINI_BASE_URL).rstrip("/")

    def is_configured(self) -> bool:
        """Return whether Gemini has the credentials required to operate."""
        return bool(self.api_key)

    def _require_api_key(self) -> str:
        """Return the configured API key, failing only when Gemini is invoked."""

        if not self.api_key:
            raise GeminiProviderNotConfiguredError("Gemini CBT AI provider is not configured")

        return self.api_key

    def _build_url(self, model: str) -> str:
        """Build the Gemini generateContent endpoint for a model."""
        return f"{self.base_url}/models/{model}:generateContent"

    async def _post(self, *, model: str, payload: dict[str, Any], timeout: float):
        """Execute a Gemini REST request and return the decoded response."""

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
    """Generate and regenerate CBT question drafts using Gemini."""

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
        """Generate a batch of CBT question drafts."""

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
                        {"text": json.dumps(dict(request), ensure_ascii=False)}
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


# IMAGE EVALUATION


class GeminiImageEvaluationProvider(_GeminiHTTPProvider, BaseImageEvaluationProvider):
    """Use Gemini vision to choose a retrieved image or request generation."""

    MAX_EVALUATION_IMAGE_BYTES = 5 * 1024 * 1024
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_output_tokens: int = 512,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self.model = model or settings.GEMINI_TEXT_MODEL
        self.timeout = timeout or settings.GEMINI_REQUEST_TIMEOUT_SECONDS
        self.max_output_tokens = max_output_tokens

    async def evaluate_images(
        self,
        *,
        requirement: str,
        candidates: Sequence[ImageCandidate],
    ) -> ProviderImageEvaluationResult:
        """Compare retrieved image candidates against one visual requirement."""

        normalized_requirement = requirement.strip()
        if not normalized_requirement:
            raise ValueError("Image requirement cannot be empty.")
        if not candidates:
            raise ValueError("At least one image candidate is required for evaluation.")

        parts: list[dict[str, Any]] = [
            {
                "text": (
                    "Evaluate the candidate images for this CBT visual requirement:\n"
                    f"{normalized_requirement}\n\n"
                    "Choose a candidate only if the visible image clearly satisfies the requirement. "
                    "If none of the images are suitable, choose generation instead. "
                    "Return JSON only in exactly this shape: "
                    '{"decision":"use_candidate|generate_image",'
                    '"selected_index":0,"reason":"short reason"}. '
                    "When decision is generate_image, selected_index must be null."
                )
            }
        ]

        loaded_indices: set[int] = set()
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for index, candidate in enumerate(candidates):
                loaded = await self._load_candidate_image(client, candidate)
                if loaded is None:
                    continue

                mime_type, data_base64 = loaded
                loaded_indices.add(index)
                parts.extend(
                    [
                        {"text": f"Candidate {index}:"},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": data_base64,
                            }
                        },
                    ]
                )

        if not loaded_indices:
            raise GeminiProviderError("Gemini could not load any image candidates for evaluation.")

        request_payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are an image suitability judge for educational CBT questions. "
                            "Judge only the visible candidate images against the supplied requirement."
                        )
                    }
                ]
            },
            "contents": [{"role": "user", "parts": parts}],
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
        result = self._parse_json_text(self._extract_text(response))

        return self._build_evaluation_result(
            result=result,
            response=response,
            allowed_indices=loaded_indices,
        )

    async def _load_candidate_image(
        self,
        client: httpx.AsyncClient,
        candidate: ImageCandidate,
    ) -> tuple[str, str] | None:
        """Load one Openverse candidate for Gemini inline image input."""

        url = candidate.thumbnail_url or candidate.image_url
        if not url:
            return None

        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        content = response.content
        if not content or len(content) > self.MAX_EVALUATION_IMAGE_BYTES:
            return None

        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in self.ALLOWED_IMAGE_TYPES:
            fallback_type = (candidate.mime_type or "").lower()
            if fallback_type not in self.ALLOWED_IMAGE_TYPES:
                return None
            content_type = fallback_type

        return content_type, base64.b64encode(content).decode("ascii")

    def _build_evaluation_result(
        self,
        *,
        result: dict[str, Any],
        response: dict[str, Any],
        allowed_indices: set[int],
    ) -> ProviderImageEvaluationResult:
        """Validate and normalize Gemini's image-selection decision."""

        decision = result.get("decision")
        selected_index = result.get("selected_index")
        reason = result.get("reason")

        if decision not in {"use_candidate", "generate_image"}:
            raise GeminiProviderError("Gemini returned an invalid image evaluation decision.")

        if decision == "use_candidate":
            if type(selected_index) is not int or selected_index not in allowed_indices:
                raise GeminiProviderError("Gemini selected an invalid image candidate index.")
        else:
            selected_index = None

        if not isinstance(reason, str):
            reason = None

        return ProviderImageEvaluationResult(
            decision=decision,
            selected_index=selected_index,
            reason=reason.strip() if reason else None,
            usage=self._extract_usage(response),
            raw_response=response,
        )


# IMAGE GENERATION


class GeminiImageGenerationProvider(_GeminiHTTPProvider, BaseImageGenerationProvider):
    """Generate CBT visual assets using Gemini's image model."""

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
                    "parts": [{"text": normalized_prompt}],
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
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
    def _extract_image(response: dict[str, Any]) -> dict[str, str]:
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
                return {"mime_type": mime_type, "data_base64": data}

        raise GeminiProviderError("Gemini returned no generated image data.")
