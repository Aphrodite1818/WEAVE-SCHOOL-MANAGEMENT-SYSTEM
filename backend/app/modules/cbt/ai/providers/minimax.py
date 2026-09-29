# ====================================== #
#             minimax.py                 #
# ====================================== #

"""MiniMax provider implementations for CBT AI question writing."""

from __future__ import annotations

import base64
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


# ==========================================================
# EXCEPTIONS
# ==========================================================


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


# ==========================================================
# SHARED MINIMAX HTTP BEHAVIOUR
# ==========================================================


class _MiniMaxHTTPProvider:
    """
    Shared REST behaviour for MiniMax-backed CBT AI providers.

    This class is internal and should not be used directly.
    """

    provider_name = "minimax"

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str | None = None,
    ) -> None:
        configured_api_key = (
            api_key
            if api_key is not None
            else settings.MINIMAX_API_KEY
        )

        if isinstance(configured_api_key, SecretStr):
            configured_api_key = configured_api_key.get_secret_value()

        self.api_key = (
            configured_api_key.strip()
            if configured_api_key
            else None
        )

        self.base_url = (
            base_url or settings.MINIMAX_BASE_URL
        ).rstrip("/")

    def is_configured(self) -> bool:
        """Return whether MiniMax has the credentials required to operate."""

        return bool(self.api_key)

    def _require_api_key(self) -> str:
        """
        Return the configured API key.

        MiniMax credentials are intentionally optional during application
        startup. Failure happens only when MiniMax is actually invoked.
        """

        if not self.api_key:
            raise MiniMaxProviderNotConfiguredError(
                "MiniMax CBT AI provider is not configured."
            )

        return self.api_key

    def _build_text_url(self) -> str:
        """Build the MiniMax text-generation endpoint."""

        return f"{self.base_url}/v1/text/chatcompletion_v2"

    def _build_image_url(self) -> str:
        """Build the MiniMax image-generation endpoint."""

        return f"{self.base_url}/v1/image_generation"

    async def _post(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        """Execute a MiniMax REST request and return the decoded response."""

        api_key = self._require_api_key()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
            ) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )

        except httpx.TimeoutException as exc:
            raise MiniMaxProviderError(
                "MiniMax request timed out."
            ) from exc

        except httpx.RequestError as exc:
            raise MiniMaxProviderError(
                "Unable to connect to MiniMax."
            ) from exc

        if response.is_error:
            raise MiniMaxProviderError(
                self._extract_error_message(response),
                status_code=response.status_code,
            )

        try:
            data = response.json()

        except ValueError as exc:
            raise MiniMaxProviderError(
                "MiniMax returned an invalid JSON response."
            ) from exc

        if not isinstance(data, dict):
            raise MiniMaxProviderError(
                "MiniMax returned an unexpected response structure."
            )

        self._raise_for_provider_error(data)

        return data

    @staticmethod
    def _extract_error_message(
        response: httpx.Response,
    ) -> str:
        """Report HTTP failure without exposing upstream credentials or content."""

        return (
            f"MiniMax request failed with HTTP "
            f"{response.status_code}."
        )

    @staticmethod
    def _raise_for_provider_error(
        response: dict[str, Any],
    ) -> None:
        """
        Detect MiniMax provider-level failures.

        MiniMax can return HTTP 200 while reporting an error inside
        `base_resp`, so HTTP status alone is not sufficient.
        """

        base_response = response.get("base_resp")

        if not isinstance(base_response, dict):
            return

        status_code = base_response.get("status_code")

        if status_code in (None, 0, "0"):
            return

        status_message = base_response.get("status_msg")

        if (
            not isinstance(status_message, str)
            or not status_message.strip()
        ):
            status_message = "MiniMax provider request failed."

        raise MiniMaxProviderError(
            status_message.strip(),
            provider_code=status_code,
        )

    @staticmethod
    def _extract_text(
        response: dict[str, Any],
    ) -> str:
        """Extract assistant text from the first MiniMax completion choice."""

        choices = response.get("choices")

        if not isinstance(choices, list) or not choices:
            raise MiniMaxProviderError(
                "MiniMax returned no completion choices."
            )

        choice = choices[0]

        if not isinstance(choice, dict):
            raise MiniMaxProviderError(
                "MiniMax returned an invalid completion choice."
            )

        message = choice.get("message")

        if not isinstance(message, dict):
            raise MiniMaxProviderError(
                "MiniMax completion contains no message."
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise MiniMaxProviderError(
                "MiniMax returned no text content."
            )

        return content.strip()

    @staticmethod
    def _parse_json_text(
        text: str,
    ) -> dict[str, Any]:
        """
        Parse JSON returned by MiniMax.

        MiniMax M3 is instructed to return JSON, but the provider
        still treats the response as untrusted text and parses it
        explicitly.
        """

        try:
            parsed = json.loads(text)

        except json.JSONDecodeError as exc:
            raise MiniMaxProviderError(
                "MiniMax returned malformed structured JSON."
            ) from exc

        if not isinstance(parsed, dict):
            raise MiniMaxProviderError(
                "MiniMax structured output must be a JSON object."
            )

        return parsed

    @staticmethod
    def _extract_usage(
        response: dict[str, Any],
    ) -> ProviderUsage:
        """Normalize MiniMax text token usage."""

        usage = response.get("usage")

        if not isinstance(usage, dict):
            return ProviderUsage()

        def token_count(key: str) -> int:
            value = usage.get(key, 0)

            return (
                value
                if type(value) is int and value >= 0
                else 0
            )

        cache_read_tokens = 0

        prompt_details = usage.get(
            "prompt_tokens_details"
        )

        if isinstance(prompt_details, dict):
            cached_tokens = prompt_details.get(
                "cached_tokens"
            )

            if (
                type(cached_tokens) is int
                and cached_tokens >= 0
            ):
                cache_read_tokens = cached_tokens

        if cache_read_tokens == 0:
            possible_cache_tokens = usage.get(
                "cache_read_tokens"
            )

            if (
                type(possible_cache_tokens) is int
                and possible_cache_tokens >= 0
            ):
                cache_read_tokens = (
                    possible_cache_tokens
                )

        return ProviderUsage(
            input_tokens=token_count(
                "prompt_tokens"
            ),
            output_tokens=token_count(
                "completion_tokens"
            ),
            cache_read_tokens=cache_read_tokens,
        )


# ==========================================================
# QUESTION GENERATION
# ==========================================================


class MiniMaxQuestionGenerationProvider(
    _MiniMaxHTTPProvider,
    BaseQuestionGenerationProvider,
):
    """Generate and regenerate CBT question drafts using MiniMax M3."""

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_output_tokens: int | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
        )

        self.model = (
            model
            or settings.MINIMAX_TEXT_MODEL
        )

        self.max_output_tokens = (
            max_output_tokens
            or settings.MINIMAX_MAX_OUTPUT_TOKENS
        )

        self.timeout = (
            timeout
            or settings.MINIMAX_REQUEST_TIMEOUT_SECONDS
        )

    async def generate_questions(
        self,
        *,
        request: Mapping[str, Any],
    ) -> ProviderQuestionGenerationResult:
        """Generate a batch of CBT question drafts."""

        request_payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a CBT educational question "
                        "authoring engine. Generate questions "
                        "strictly from the supplied academic "
                        "context and author instructions. "
                        "Return only valid JSON. "
                        "The top-level JSON object must contain "
                        "a 'questions' array. "
                        "Do not wrap the response in markdown, "
                        "code fences, commentary, or explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        dict(request),
                        ensure_ascii=False,
                    ),
                },
            ],
            "max_tokens": self.max_output_tokens,
            "stream": False,
            "thinking": {
                "type": "disabled",
            },
        }

        response = await self._post(
            url=self._build_text_url(),
            payload=request_payload,
            timeout=self.timeout,
        )

        text = self._extract_text(response)

        result = self._parse_json_text(
            text
        )

        questions = result.get(
            "questions"
        )

        if (
            not isinstance(questions, list)
            or any(
                not isinstance(question, dict)
                for question in questions
            )
        ):
            raise MiniMaxProviderError(
                "MiniMax question-generation response does not "
                "contain a valid 'questions' array of objects."
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
    ) -> ProviderQuestionRegenerationResult:
        """Regenerate or transform one existing CBT question draft."""

        request_payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a CBT educational question "
                        "editing engine. Transform exactly one "
                        "existing question using the supplied "
                        "academic context and transformation "
                        "instruction. Preserve constraints such "
                        "as subject, level, topic and question "
                        "type unless the request explicitly "
                        "allows a change. "
                        "Return only valid JSON. "
                        "The top-level JSON object must contain "
                        "a 'question' object. "
                        "Do not wrap the response in markdown, "
                        "code fences, commentary, or explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        dict(request),
                        ensure_ascii=False,
                    ),
                },
            ],
            "max_tokens": self.max_output_tokens,
            "stream": False,
            "thinking": {
                "type": "disabled",
            },
        }

        response = await self._post(
            url=self._build_text_url(),
            payload=request_payload,
            timeout=self.timeout,
        )

        text = self._extract_text(response)

        result = self._parse_json_text(
            text
        )

        question = result.get(
            "question"
        )

        if not isinstance(
            question,
            dict,
        ):
            raise MiniMaxProviderError(
                "MiniMax regeneration response does not contain "
                "a valid 'question' object."
            )

        return ProviderQuestionRegenerationResult(
            question=question,
            usage=self._extract_usage(response),
            raw_response=response,
        )


# ==========================================================
# IMAGE GENERATION
# ==========================================================


class MiniMaxImageGenerationProvider(
    _MiniMaxHTTPProvider,
    BaseImageGenerationProvider,
):
    """Generate CBT visual assets using MiniMax Image-01."""

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
        )

        self.model = (
            model
            or settings.MINIMAX_IMAGE_MODEL
        )

        self.timeout = (
            timeout
            or settings.MINIMAX_IMAGE_TIMEOUT_SECONDS
        )

    async def generate_image(
        self,
        *,
        prompt: str,
        metadata: Mapping[str, Any] | None = None,
        reference_images: Sequence[str] | None = None,
    ) -> ProviderImageGenerationResult:
        """Generate a single image from a CBT visual prompt."""

        normalized_prompt = (
            prompt.strip()
        )

        if not normalized_prompt:
            raise ValueError(
                "Image generation prompt cannot be empty."
            )

        if reference_images:
            raise ValueError(
                "Reference images are not supported by this "
                "provider yet."
            )

        aspect_ratio = "1:1"

        if metadata:
            requested_aspect_ratio = (
                metadata.get("aspect_ratio")
            )

            if requested_aspect_ratio is not None:
                if (
                    not isinstance(
                        requested_aspect_ratio,
                        str,
                    )
                    or requested_aspect_ratio
                    not in {
                        "1:1",
                        "16:9",
                        "4:3",
                        "3:2",
                        "2:3",
                        "3:4",
                        "9:16",
                        "21:9",
                    }
                ):
                    raise ValueError(
                        "Unsupported MiniMax image aspect ratio."
                    )

                aspect_ratio = (
                    requested_aspect_ratio
                )

            prompt_metadata = {
                key: value
                for key, value in metadata.items()
                if key != "aspect_ratio"
            }

            if prompt_metadata:
                normalized_prompt += (
                    "\nImage context: "
                    + json.dumps(
                        prompt_metadata,
                        ensure_ascii=False,
                    )
                )

        if len(normalized_prompt) > 1500:
            raise ValueError(
                "MiniMax image generation prompt cannot "
                "exceed 1500 characters."
            )

        request_payload = {
            "model": self.model,
            "prompt": normalized_prompt,
            "aspect_ratio": aspect_ratio,
            "n": 1,
            "response_format": "base64",
            "prompt_optimizer": False,
        }

        response = await self._post(
            url=self._build_image_url(),
            payload=request_payload,
            timeout=self.timeout,
        )

        image = self._extract_image(
            response
        )

        return ProviderImageGenerationResult(
            image=ProviderGeneratedImage(
                content_type=image[
                    "content_type"
                ],
                data_base64=image[
                    "data_base64"
                ],
            ),
            usage=ProviderUsage(),
            raw_response=response,
        )

    @classmethod
    def _extract_image(
        cls,
        response: dict[str, Any],
    ) -> dict[str, str]:
        """Extract the first generated base64 image returned by MiniMax."""

        data = response.get(
            "data"
        )

        if not isinstance(
            data,
            dict,
        ):
            raise MiniMaxProviderError(
                "MiniMax image response contains no data."
            )

        images = data.get(
            "image_base64"
        )

        if (
            not isinstance(images, list)
            or not images
        ):
            raise MiniMaxProviderError(
                "MiniMax returned no generated image data."
            )

        image_data = images[0]

        if (
            not isinstance(image_data, str)
            or not image_data
        ):
            raise MiniMaxProviderError(
                "MiniMax returned invalid generated image data."
            )

        content_type = (
            cls._detect_image_content_type(
                image_data
            )
        )

        return {
            "content_type": content_type,
            "data_base64": image_data,
        }

    @staticmethod
    def _detect_image_content_type(
        image_data: str,
    ) -> str:
        """Detect the MIME type of a base64 MiniMax image."""

        try:
            raw = base64.b64decode(
                image_data,
                validate=True,
            )

        except (ValueError, TypeError) as exc:
            raise MiniMaxProviderError(
                "MiniMax returned invalid base64 image data."
            ) from exc

        if raw.startswith(
            b"\xff\xd8\xff"
        ):
            return "image/jpeg"

        if raw.startswith(
            b"\x89PNG\r\n\x1a\n"
        ):
            return "image/png"

        if (
            raw.startswith(b"RIFF")
            and len(raw) >= 12
            and raw[8:12] == b"WEBP"
        ):
            return "image/webp"

        raise MiniMaxProviderError(
            "MiniMax returned an unsupported image format."
        )