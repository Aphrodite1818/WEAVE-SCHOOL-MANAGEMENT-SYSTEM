"""Gemini provider implementations for CBT AI question writing."""

from __future__ import annotations

import base64
import json
from typing import Any, Mapping, Sequence

import httpx
from pydantic import SecretStr

from app.config.settings import settings
from app.modules.cbt.ai.authoring.contracts import (
    build_question_generation_prompt,
    build_question_regeneration_prompt,
    build_question_repair_prompt,
)
from app.modules.cbt.ai.authoring.providers.base import (
    BaseImageEvaluationProvider,
    BaseImageGenerationProvider,
    BaseQuestionGenerationProvider,
    ProviderGeneratedImage,
    ProviderImageEvaluationResult,
    ProviderImageGenerationResult,
    ProviderImageInput,
    ProviderQuestionGenerationResult,
    ProviderQuestionRegenerationResult,
    ProviderUsage,
)


class GeminiProviderError(RuntimeError):
    """Raised when Gemini cannot successfully complete a provider request."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GeminiProviderNotConfiguredError(GeminiProviderError):
    """Raised when Gemini is invoked without an API key."""


class _GeminiHTTPProvider:
    provider_name = "gemini"

    def __init__(self, *, api_key: SecretStr | str | None = None, base_url: str | None = None):
        configured_api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        if isinstance(configured_api_key, SecretStr):
            configured_api_key = configured_api_key.get_secret_value()
        self.api_key = configured_api_key.strip() if configured_api_key else None
        self.base_url = (base_url or settings.GEMINI_BASE_URL).rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _require_api_key(self) -> str:
        if not self.api_key:
            raise GeminiProviderNotConfiguredError("Gemini CBT AI provider is not configured")
        return self.api_key

    def _build_url(self, model: str) -> str:
        return f"{self.base_url}/models/{model}:generateContent"

    async def _post(self, *, model: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        headers = {
            "x-goog-api-key": self._require_api_key(),
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self._build_url(model), headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise GeminiProviderError("Gemini request timed out") from exc
        except httpx.RequestError as exc:
            raise GeminiProviderError("Unable to connect to Gemini") from exc

        if response.is_error:
            raise GeminiProviderError(
                f"Gemini request failed with HTTP {response.status_code}",
                status_code=response.status_code,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise GeminiProviderError("Gemini returned an invalid JSON response") from exc
        if not isinstance(data, dict):
            raise GeminiProviderError("Gemini returned an unexpected response structure")
        return data

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
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
        text_parts = [
            part["text"]
            for part in parts
            if isinstance(part, dict)
            and not part.get("thought")
            and isinstance(part.get("text"), str)
            and part["text"].strip()
        ]
        if not text_parts:
            raise GeminiProviderError("Gemini returned no text content.")
        return "".join(text_parts).strip()

    @staticmethod
    def _parse_json_text(text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiProviderError("Gemini returned malformed structured JSON.") from exc
        if not isinstance(parsed, dict):
            raise GeminiProviderError("Gemini structured output must be a JSON object.")
        return parsed

    @staticmethod
    def _extract_usage(response: dict[str, Any]) -> ProviderUsage:
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

    @staticmethod
    def _image_part(image: ProviderImageInput) -> dict[str, Any]:
        return {
            "inlineData": {
                "mimeType": image.content_type,
                "data": base64.b64encode(image.data).decode("ascii"),
            }
        }


class GeminiQuestionGenerationProvider(_GeminiHTTPProvider, BaseQuestionGenerationProvider):
    """Generate/regenerate questions while accepting canonical image bytes."""

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

    def _user_parts(
        self,
        request: Mapping[str, Any],
        reference_images: Sequence[ProviderImageInput] | None,
    ) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = [
            {"text": json.dumps(dict(request), ensure_ascii=False)}
        ]
        for index, image in enumerate(reference_images or ()):
            label = image.label or f"reference_image_{index}"
            parts.append({"text": f"Reference image `{label}`:"})
            parts.append(self._image_part(image))
        return parts

    async def _structured_call(
        self,
        *,
        system_prompt: str,
        request: Mapping[str, Any],
        reference_images: Sequence[ProviderImageInput] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {"role": "user", "parts": self._user_parts(request, reference_images)}
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": self.max_output_tokens,
            },
        }
        response = await self._post(model=self.model, payload=payload, timeout=self.timeout)
        return self._parse_json_text(self._extract_text(response)), response

    async def generate_questions(
        self,
        *,
        request: Mapping[str, Any],
    ) -> ProviderQuestionGenerationResult:
        result, response = await self._structured_call(
            system_prompt=build_question_generation_prompt(),
            request=request,
        )
        questions = result.get("questions")
        if not isinstance(questions, list) or any(not isinstance(q, dict) for q in questions):
            raise GeminiProviderError(
                "Gemini question-generation response does not contain a valid 'questions' array of objects."
            )
        return ProviderQuestionGenerationResult(
            questions=questions,
            usage=self._extract_usage(response),
            raw_response=response,
        )

    async def repair_questions(
        self,
        *,
        request: Mapping[str, Any],
        reference_images: Sequence[ProviderImageInput] | None = None,
    ) -> ProviderQuestionGenerationResult:
        result, response = await self._structured_call(
            system_prompt=build_question_repair_prompt(),
            request=request,
            reference_images=reference_images,
        )
        questions = result.get("questions")
        if not isinstance(questions, list) or any(not isinstance(q, dict) for q in questions):
            raise GeminiProviderError(
                "Gemini question-repair response does not contain a valid 'questions' array of objects."
            )
        return ProviderQuestionGenerationResult(
            questions=questions,
            usage=self._extract_usage(response),
            raw_response=response,
        )

    async def regenerate_question(
        self,
        *,
        request: Mapping[str, Any],
        reference_images: Sequence[ProviderImageInput] | None = None,
    ) -> ProviderQuestionRegenerationResult:
        result, response = await self._structured_call(
            system_prompt=build_question_regeneration_prompt(),
            request=request,
            reference_images=reference_images,
        )
        question = result.get("question")
        if not isinstance(question, dict):
            raise GeminiProviderError(
                "Gemini regeneration response does not contain a valid 'question' object."
            )
        return ProviderQuestionRegenerationResult(
            question=question,
            usage=self._extract_usage(response),
            raw_response=response,
        )


class GeminiImageEvaluationProvider(_GeminiHTTPProvider, BaseImageEvaluationProvider):
    """Use Gemini vision to judge already-materialized candidate image bytes."""

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
        images: Sequence[ProviderImageInput],
    ) -> ProviderImageEvaluationResult:
        normalized_requirement = requirement.strip()
        if not normalized_requirement:
            raise ValueError("Image requirement cannot be empty.")
        if not images:
            raise ValueError("At least one materialized image is required for evaluation.")

        parts: list[dict[str, Any]] = [
            {
                "text": (
                    "Evaluate the candidate images for this CBT visual requirement:\n"
                    f"{normalized_requirement}\n\n"
                    "Choose a candidate only if the visible image clearly satisfies the requirement. "
                    "If none are suitable, choose generation. Return JSON only as "
                    '{"decision":"use_candidate|generate_image","selected_index":0,'
                    '"reason":"short reason"}. When generating, selected_index must be null.'
                )
            }
        ]
        for index, image in enumerate(images):
            parts.append({"text": f"Candidate {index}:"})
            parts.append(self._image_part(image))

        payload = {
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
        response = await self._post(model=self.model, payload=payload, timeout=self.timeout)
        result = self._parse_json_text(self._extract_text(response))
        decision = result.get("decision")
        selected_index = result.get("selected_index")
        reason = result.get("reason")

        if decision not in {"use_candidate", "generate_image"}:
            raise GeminiProviderError("Gemini returned an invalid image evaluation decision.")
        if decision == "use_candidate":
            if type(selected_index) is not int or not 0 <= selected_index < len(images):
                raise GeminiProviderError("Gemini selected an invalid image candidate index.")
        else:
            selected_index = None
        return ProviderImageEvaluationResult(
            decision=decision,
            selected_index=selected_index,
            reason=reason.strip() if isinstance(reason, str) and reason.strip() else None,
            usage=self._extract_usage(response),
            raw_response=response,
        )


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
        reference_images: Sequence[ProviderImageInput] | None = None,
    ) -> ProviderImageGenerationResult:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Image generation prompt cannot be empty.")
        if metadata:
            normalized_prompt += "\nImage context: " + json.dumps(dict(metadata), ensure_ascii=False)

        parts: list[dict[str, Any]] = [{"text": normalized_prompt}]
        for index, image in enumerate(reference_images or ()):
            label = image.label or f"reference_image_{index}"
            parts.append({"text": f"Reference image `{label}`:"})
            parts.append(self._image_part(image))

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        response = await self._post(model=self.model, payload=payload, timeout=self.timeout)
        image = self._extract_image(response)
        return ProviderImageGenerationResult(
            image=ProviderGeneratedImage(
                content_type=image["mime_type"],
                data_base64=image["data_base64"],
            ),
            usage=self._extract_usage(response),
            raw_response=response,
        )

    @staticmethod
    def _extract_image(response: dict[str, Any]) -> dict[str, str]:
        candidates = response.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise GeminiProviderError("Gemini returned no image candidates.")
        candidate = candidates[0]
        content = candidate.get("content") if isinstance(candidate, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            raise GeminiProviderError("Gemini image candidate contains no parts.")
        for part in parts:
            inline_data = part.get("inlineData") if isinstance(part, dict) else None
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
