"""MiniMax provider implementations for CBT AI question writing."""

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


class MiniMaxProviderError(RuntimeError):
    """Raised when MiniMax cannot successfully complete a provider request."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider_code: int | str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_code = provider_code


class MiniMaxProviderNotConfiguredError(MiniMaxProviderError):
    """Raised when MiniMax is invoked without an API key."""


class _MiniMaxHTTPProvider:
    provider_name = "minimax"

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str | None = None,
    ) -> None:
        configured_api_key = api_key if api_key is not None else settings.MINIMAX_API_KEY
        if isinstance(configured_api_key, SecretStr):
            configured_api_key = configured_api_key.get_secret_value()
        self.api_key = configured_api_key.strip() if configured_api_key else None
        self.base_url = (base_url or settings.MINIMAX_BASE_URL).rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _require_api_key(self) -> str:
        if not self.api_key:
            raise MiniMaxProviderNotConfiguredError("MiniMax CBT AI provider is not configured.")
        return self.api_key

    def _build_text_url(self) -> str:
        return f"{self.base_url}/v1/text/chatcompletion_v2"

    def _build_image_url(self) -> str:
        return f"{self.base_url}/v1/image_generation"

    async def _post(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._require_api_key()}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise MiniMaxProviderError("MiniMax request timed out.") from exc
        except httpx.RequestError as exc:
            raise MiniMaxProviderError("Unable to connect to MiniMax.") from exc
        if response.is_error:
            raise MiniMaxProviderError(
                f"MiniMax request failed with HTTP {response.status_code}.",
                status_code=response.status_code,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise MiniMaxProviderError("MiniMax returned an invalid JSON response.") from exc
        if not isinstance(data, dict):
            raise MiniMaxProviderError("MiniMax returned an unexpected response structure.")
        self._raise_for_provider_error(data)
        return data

    @staticmethod
    def _raise_for_provider_error(response: dict[str, Any]) -> None:
        base_response = response.get("base_resp")
        if not isinstance(base_response, dict):
            return
        status_code = base_response.get("status_code")
        if status_code in (None, 0, "0"):
            return
        message = base_response.get("status_msg")
        raise MiniMaxProviderError(
            message.strip() if isinstance(message, str) and message.strip() else "MiniMax provider request failed.",
            provider_code=status_code,
        )

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise MiniMaxProviderError("MiniMax returned no completion choices.")
        choice = choices[0]
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise MiniMaxProviderError("MiniMax returned no text content.")
        return content.strip()

    @staticmethod
    def _parse_json_text(text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MiniMaxProviderError("MiniMax returned malformed structured JSON.") from exc
        if not isinstance(parsed, dict):
            raise MiniMaxProviderError("MiniMax structured output must be a JSON object.")
        return parsed

    @staticmethod
    def _extract_usage(response: dict[str, Any]) -> ProviderUsage:
        usage = response.get("usage")
        if not isinstance(usage, dict):
            return ProviderUsage()

        def token_count(key: str) -> int:
            value = usage.get(key, 0)
            return value if type(value) is int and value >= 0 else 0

        cache_read_tokens = 0
        prompt_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_details, dict):
            cached = prompt_details.get("cached_tokens")
            if type(cached) is int and cached >= 0:
                cache_read_tokens = cached
        if cache_read_tokens == 0:
            cached = usage.get("cache_read_tokens")
            if type(cached) is int and cached >= 0:
                cache_read_tokens = cached
        return ProviderUsage(
            input_tokens=token_count("prompt_tokens"),
            output_tokens=token_count("completion_tokens"),
            cache_read_tokens=cache_read_tokens,
        )

    @staticmethod
    def _data_uri(image: ProviderImageInput) -> str:
        encoded = base64.b64encode(image.data).decode("ascii")
        return f"data:{image.content_type};base64,{encoded}"


class MiniMaxQuestionGenerationProvider(_MiniMaxHTTPProvider, BaseQuestionGenerationProvider):
    """Generate/regenerate questions while accepting canonical image bytes."""

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_output_tokens: int | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self.model = model or settings.MINIMAX_TEXT_MODEL
        self.max_output_tokens = max_output_tokens or settings.MINIMAX_MAX_OUTPUT_TOKENS
        self.timeout = timeout or settings.MINIMAX_REQUEST_TIMEOUT_SECONDS

    def _user_content(
        self,
        request: Mapping[str, Any],
        reference_images: Sequence[ProviderImageInput] | None,
    ) -> str | list[dict[str, Any]]:
        text = json.dumps(dict(request), ensure_ascii=False)
        if not reference_images:
            return text
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for index, image in enumerate(reference_images):
            label = image.label or f"reference_image_{index}"
            content.append({"type": "text", "text": f"Reference image `{label}`:"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": self._data_uri(image), "detail": "default"},
                }
            )
        return content

    async def _structured_call(
        self,
        *,
        system_prompt: str,
        request: Mapping[str, Any],
        reference_images: Sequence[ProviderImageInput] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self._user_content(request, reference_images)},
            ],
            "max_tokens": self.max_output_tokens,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        response = await self._post(
            url=self._build_text_url(), payload=payload, timeout=self.timeout
        )
        return self._parse_json_text(self._extract_text(response)), response

    async def generate_questions(
        self,
        *,
        request: Mapping[str, Any],
    ) -> ProviderQuestionGenerationResult:
        result, response = await self._structured_call(
            system_prompt=build_question_generation_prompt(), request=request
        )
        questions = result.get("questions")
        if not isinstance(questions, list) or any(not isinstance(q, dict) for q in questions):
            raise MiniMaxProviderError(
                "MiniMax question-generation response does not contain a valid 'questions' array of objects."
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
            raise MiniMaxProviderError(
                "MiniMax question-repair response does not contain a valid 'questions' array of objects."
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
            raise MiniMaxProviderError(
                "MiniMax regeneration response does not contain a valid 'question' object."
            )
        return ProviderQuestionRegenerationResult(
            question=question,
            usage=self._extract_usage(response),
            raw_response=response,
        )


class MiniMaxImageEvaluationProvider(_MiniMaxHTTPProvider, BaseImageEvaluationProvider):
    """Use MiniMax vision to judge materialized image bytes."""

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
        self.model = model or settings.MINIMAX_TEXT_MODEL
        self.timeout = timeout or settings.MINIMAX_REQUEST_TIMEOUT_SECONDS
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

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Evaluate the candidate images for this CBT visual requirement:\n"
                    f"{normalized_requirement}\n\n"
                    "Choose a candidate only if the visible image clearly satisfies the requirement. "
                    "If none are suitable, choose generation. Return JSON only as "
                    '{"decision":"use_candidate|generate_image","selected_index":0,'
                    '"reason":"short reason"}. When generating, selected_index must be null.'
                ),
            }
        ]
        for index, image in enumerate(images):
            content.extend(
                [
                    {"type": "text", "text": f"Candidate {index}:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": self._data_uri(image), "detail": "default"},
                    },
                ]
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an image suitability judge for educational CBT questions. "
                        "Judge only the visible candidate images against the supplied requirement."
                    ),
                },
                {"role": "user", "content": content},
            ],
            "max_tokens": self.max_output_tokens,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        response = await self._post(
            url=self._build_text_url(), payload=payload, timeout=self.timeout
        )
        result = self._parse_json_text(self._extract_text(response))
        decision = result.get("decision")
        selected_index = result.get("selected_index")
        reason = result.get("reason")

        if decision not in {"use_candidate", "generate_image"}:
            raise MiniMaxProviderError("MiniMax returned an invalid image evaluation decision.")
        if decision == "use_candidate":
            if type(selected_index) is not int or not 0 <= selected_index < len(images):
                raise MiniMaxProviderError("MiniMax selected an invalid image candidate index.")
        else:
            selected_index = None
        return ProviderImageEvaluationResult(
            decision=decision,
            selected_index=selected_index,
            reason=reason.strip() if isinstance(reason, str) and reason.strip() else None,
            usage=self._extract_usage(response),
            raw_response=response,
        )


class MiniMaxImageGenerationProvider(_MiniMaxHTTPProvider, BaseImageGenerationProvider):
    """Generate CBT visual assets using MiniMax Image-01."""

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self.model = model or settings.MINIMAX_IMAGE_MODEL
        self.timeout = timeout or settings.MINIMAX_IMAGE_TIMEOUT_SECONDS

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
        if reference_images:
            raise ValueError("MiniMax image generation does not support reference images in this adapter.")

        aspect_ratio = "1:1"
        if metadata:
            requested = metadata.get("aspect_ratio")
            if requested is not None:
                allowed = {"1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"}
                if not isinstance(requested, str) or requested not in allowed:
                    raise ValueError("Unsupported MiniMax image aspect ratio.")
                aspect_ratio = requested
            prompt_metadata = {k: v for k, v in metadata.items() if k != "aspect_ratio"}
            if prompt_metadata:
                normalized_prompt += "\nImage context: " + json.dumps(
                    prompt_metadata, ensure_ascii=False
                )
        if len(normalized_prompt) > 1500:
            raise ValueError("MiniMax image generation prompt cannot exceed 1500 characters.")

        payload = {
            "model": self.model,
            "prompt": normalized_prompt,
            "aspect_ratio": aspect_ratio,
            "n": 1,
            "response_format": "base64",
            "prompt_optimizer": False,
        }
        response = await self._post(
            url=self._build_image_url(), payload=payload, timeout=self.timeout
        )
        image = self._extract_image(response)
        return ProviderImageGenerationResult(
            image=ProviderGeneratedImage(
                content_type=image["content_type"], data_base64=image["data_base64"]
            ),
            usage=ProviderUsage(),
            raw_response=response,
        )

    @classmethod
    def _extract_image(cls, response: dict[str, Any]) -> dict[str, str]:
        data = response.get("data")
        images = data.get("image_base64") if isinstance(data, dict) else None
        if not isinstance(images, list) or not images:
            raise MiniMaxProviderError("MiniMax returned no generated image data.")
        image_data = images[0]
        if not isinstance(image_data, str) or not image_data:
            raise MiniMaxProviderError("MiniMax returned invalid generated image data.")
        return {
            "content_type": cls._detect_image_content_type(image_data),
            "data_base64": image_data,
        }

    @staticmethod
    def _detect_image_content_type(image_data: str) -> str:
        try:
            raw = base64.b64decode(image_data, validate=True)
        except (ValueError, TypeError) as exc:
            raise MiniMaxProviderError("MiniMax returned invalid base64 image data.") from exc
        if raw.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if raw.startswith(b"RIFF") and len(raw) >= 12 and raw[8:12] == b"WEBP":
            return "image/webp"
        raise MiniMaxProviderError("MiniMax returned an unsupported image format.")
