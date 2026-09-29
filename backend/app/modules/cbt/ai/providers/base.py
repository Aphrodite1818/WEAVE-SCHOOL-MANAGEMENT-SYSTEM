from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence


@dataclass(slots=True)
class ProviderUsage:
    """Normalized usage/cost metadata returned by a provider call."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0

    # Optional provider-side calculated cost, if available.
    provider_cost: float | None = None
    currency: str | None = "USD"


@dataclass(slots=True)
class ProviderQuestionGenerationResult:
    """Result returned when a provider generates a batch of draft questions."""

    questions: list[dict[str, Any]]
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    raw_response: dict[str, Any] | None = None


@dataclass(slots=True)
class ProviderQuestionRegenerationResult:
    """Result returned when a provider regenerates/transforms one draft question."""

    question: dict[str, Any]
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    raw_response: dict[str, Any] | None = None


@dataclass(slots=True)
class ProviderGeneratedImage:
    """Normalized image returned by an image-generation provider."""

    content_type: str
    data_base64: str | None = None
    url: str | None = None

    width: int | None = None
    height: int | None = None
    alt_text: str | None = None


@dataclass(slots=True)
class ProviderImageGenerationResult:
    """Result returned when a provider generates one image."""

    image: ProviderGeneratedImage
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    raw_response: dict[str, Any] | None = None


@dataclass(slots=True)
class ImageCandidate:
    """Normalized sourced-image candidate returned by a search provider."""

    source: str
    source_url: str

    external_id: str | None = None
    title: str | None = None

    image_url: str | None = None
    thumbnail_url: str | None = None

    creator: str | None = None
    attribution_text: str | None = None

    license_name: str | None = None
    license_url: str | None = None

    width: int | None = None
    height: int | None = None
    mime_type: str | None = None


@dataclass(slots=True)
class ProviderImageEvaluationResult:
    """Decision returned after a vision-capable provider reviews image candidates."""

    decision: Literal["use_candidate", "generate_image"]
    selected_index: int | None = None
    reason: str | None = None
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    raw_response: dict[str, Any] | None = None


@dataclass(slots=True)
class ImageResolutionResult:
    """Final result produced by the provider-agnostic image resolver."""

    source: Literal["search", "generated"]
    candidate: ImageCandidate | None = None
    generation: ProviderImageGenerationResult | None = None
    evaluation: ProviderImageEvaluationResult | None = None


class BaseProvider(ABC):
    """Base provider class for all CBT AI providers."""

    provider_name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Return True when the provider has the minimum configuration required.

        Missing optional AI credentials must not block application startup;
        concrete providers should fail only when the capability is invoked.
        """
        raise NotImplementedError


class BaseQuestionGenerationProvider(BaseProvider, ABC):
    """Contract for providers that generate or transform CBT question drafts."""

    @abstractmethod
    async def generate_questions(
        self,
        *,
        request: Mapping[str, Any],
    ) -> ProviderQuestionGenerationResult:
        """Generate a batch of draft questions."""
        raise NotImplementedError

    @abstractmethod
    async def regenerate_question(
        self,
        *,
        request: Mapping[str, Any],
    ) -> ProviderQuestionRegenerationResult:
        """Regenerate or transform one existing draft question."""
        raise NotImplementedError


class BaseImageGenerationProvider(BaseProvider, ABC):
    """Contract for providers that generate new visual assets."""

    @abstractmethod
    async def generate_image(
        self,
        *,
        prompt: str,
        metadata: Mapping[str, Any] | None = None,
        reference_images: Sequence[str] | None = None,
    ) -> ProviderImageGenerationResult:
        """Generate one image."""
        raise NotImplementedError


class BaseImageSearchProvider(BaseProvider, ABC):
    """Contract for providers that retrieve existing image candidates."""

    @abstractmethod
    async def search(
        self,
        *,
        query: str,
        limit: int = 10,
        metadata: Mapping[str, Any] | None = None,
    ) -> list[ImageCandidate]:
        """Search for candidate images."""
        raise NotImplementedError


class BaseImageEvaluationProvider(BaseProvider, ABC):
    """Contract for vision-capable providers that judge retrieved images."""

    @abstractmethod
    async def evaluate_images(
        self,
        *,
        requirement: str,
        candidates: Sequence[ImageCandidate],
    ) -> ProviderImageEvaluationResult:
        """
        Decide whether one candidate satisfies the requirement.

        The selected index always refers to the position inside `candidates`.
        If no candidate is suitable, return the `generate_image` decision.
        """
        raise NotImplementedError
