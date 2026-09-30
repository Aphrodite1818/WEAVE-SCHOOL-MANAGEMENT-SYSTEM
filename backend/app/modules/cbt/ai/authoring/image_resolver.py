"""Provider-agnostic image resolution engine for CBT AI authoring."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.modules.cbt.ai.authoring.providers.base import (
    BaseImageEvaluationProvider,
    BaseImageGenerationProvider,
    BaseImageSearchProvider,
    ImageResolutionResult,
    ProviderImageEvaluationResult,
)


class ImageResolverError(RuntimeError):
    """Raised when providers return an invalid image-resolution decision."""


class ImageResolver:
    """
    Resolve a CBT visual requirement through search, evaluation and generation.

    The engine does not know which concrete providers are in use. It preserves
    the search provider's ranking, reviews only the first few candidates, and
    generates an image only when search produces no candidates or the active
    evaluation provider rejects every reviewed candidate.
    """

    DEFAULT_SEARCH_LIMIT = 10
    DEFAULT_REVIEW_LIMIT = 3

    def __init__(
        self,
        *,
        search_provider: BaseImageSearchProvider,
        evaluation_provider: BaseImageEvaluationProvider,
        generation_provider: BaseImageGenerationProvider,
        search_limit: int = DEFAULT_SEARCH_LIMIT,
        review_limit: int = DEFAULT_REVIEW_LIMIT,
    ) -> None:
        if type(search_limit) is not int or search_limit <= 0:
            raise ValueError("Image search limit must be a positive integer.")
        if type(review_limit) is not int or review_limit <= 0:
            raise ValueError("Image review limit must be a positive integer.")
        if review_limit > search_limit:
            raise ValueError("Image review limit cannot exceed the search limit.")

        self.search_provider = search_provider
        self.evaluation_provider = evaluation_provider
        self.generation_provider = generation_provider
        self.search_limit = search_limit
        self.review_limit = review_limit

    async def resolve(
        self,
        *,
        requirement: str,
        search_query: str,
        generation_prompt: str | None = None,
        search_metadata: Mapping[str, Any] | None = None,
        generation_metadata: Mapping[str, Any] | None = None,
        reference_images: Sequence[str] | None = None,
    ) -> ImageResolutionResult:
        """Resolve one requested visual into a sourced or generated image."""

        normalized_requirement = requirement.strip()
        normalized_search_query = search_query.strip()

        if not normalized_requirement:
            raise ValueError("Image requirement cannot be empty.")
        if not normalized_search_query:
            raise ValueError("Image search query cannot be empty.")

        normalized_generation_prompt = (
            generation_prompt.strip()
            if isinstance(generation_prompt, str) and generation_prompt.strip()
            else normalized_requirement
        )

        candidates = await self.search_provider.search(
            query=normalized_search_query,
            limit=self.search_limit,
            metadata=search_metadata,
        )

        review_candidates = candidates[: self.review_limit]

        if not review_candidates:
            return await self._generate(
                prompt=normalized_generation_prompt,
                metadata=generation_metadata,
                reference_images=reference_images,
                evaluation=None,
            )

        evaluation = await self.evaluation_provider.evaluate_images(
            requirement=normalized_requirement,
            candidates=review_candidates,
        )

        if evaluation.decision == "generate_image":
            return await self._generate(
                prompt=normalized_generation_prompt,
                metadata=generation_metadata,
                reference_images=reference_images,
                evaluation=evaluation,
            )

        if evaluation.decision != "use_candidate":
            raise ImageResolverError(
                f"Unsupported image evaluation decision: {evaluation.decision!r}."
            )

        selected_index = evaluation.selected_index
        if (
            type(selected_index) is not int
            or selected_index < 0
            or selected_index >= len(review_candidates)
        ):
            raise ImageResolverError(
                "Image evaluation provider selected an invalid candidate index."
            )

        return ImageResolutionResult(
            source="search",
            candidate=review_candidates[selected_index],
            evaluation=evaluation,
        )

    async def _generate(
        self,
        *,
        prompt: str,
        metadata: Mapping[str, Any] | None,
        reference_images: Sequence[str] | None,
        evaluation: ProviderImageEvaluationResult | None,
    ) -> ImageResolutionResult:
        """Generate the fallback image using the injected generation provider."""

        generation = await self.generation_provider.generate_image(
            prompt=prompt,
            metadata=metadata,
            reference_images=reference_images,
        )

        return ImageResolutionResult(
            source="generated",
            generation=generation,
            evaluation=evaluation,
        )
