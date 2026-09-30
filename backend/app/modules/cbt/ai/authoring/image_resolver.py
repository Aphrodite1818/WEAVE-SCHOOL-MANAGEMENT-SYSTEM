"""Provider-agnostic image resolution engine for CBT AI authoring."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.modules.cbt.ai.authoring.image_materializer import (
    ImageMaterializationError,
    ImageMaterializer,
)
from app.modules.cbt.ai.authoring.providers.base import (
    BaseImageEvaluationProvider,
    BaseImageGenerationProvider,
    BaseImageSearchProvider,
    ImageCandidate,
    ImageResolutionResult,
    ProviderImageEvaluationResult,
    ProviderImageInput,
)


class ImageResolverError(RuntimeError):
    """Raised when providers return an invalid image-resolution decision."""


class ImageResolver:
    """Resolve CBT visual requirements into fully materialized image bytes.

    URLs and provider Base64 are transient inputs only. If resolve() returns
    successfully, ImageResolutionResult.image contains validated encoded image
    file bytes that can be sent to CBT or another provider without performing
    another external download.
    """

    DEFAULT_SEARCH_LIMIT = 10
    DEFAULT_REVIEW_LIMIT = 3

    def __init__(
        self,
        *,
        search_provider: BaseImageSearchProvider,
        evaluation_provider: BaseImageEvaluationProvider,
        generation_provider: BaseImageGenerationProvider,
        materializer: ImageMaterializer,
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
        self.materializer = materializer
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
        reference_images: Sequence[ProviderImageInput] | None = None,
    ) -> ImageResolutionResult:
        """Resolve one requested visual into sourced or generated image bytes."""

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

        materialized_candidates = await self._materialize_review_candidates(
            candidates[: self.review_limit]
        )

        if not materialized_candidates:
            return await self._generate(
                prompt=normalized_generation_prompt,
                metadata=generation_metadata,
                reference_images=reference_images,
                evaluation=None,
            )

        evaluation = await self.evaluation_provider.evaluate_images(
            requirement=normalized_requirement,
            images=[image for _, image in materialized_candidates],
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
            or selected_index >= len(materialized_candidates)
        ):
            raise ImageResolverError(
                "Image evaluation provider selected an invalid candidate index."
            )

        selected_candidate, selected_image = materialized_candidates[selected_index]
        return ImageResolutionResult(
            source="search",
            image=selected_image,
            candidate=selected_candidate,
            evaluation=evaluation,
        )

    async def _materialize_review_candidates(
        self,
        candidates: Sequence[ImageCandidate],
    ) -> list[tuple[ImageCandidate, ProviderImageInput]]:
        """Discard inaccessible/invalid candidates before vision evaluation."""

        materialized: list[tuple[ImageCandidate, ProviderImageInput]] = []
        for candidate in candidates:
            try:
                image = await self.materializer.materialize_candidate(
                    candidate,
                    label=f"search_candidate_{len(materialized)}",
                )
            except ImageMaterializationError:
                continue
            materialized.append((candidate, image))
        return materialized

    async def _generate(
        self,
        *,
        prompt: str,
        metadata: Mapping[str, Any] | None,
        reference_images: Sequence[ProviderImageInput] | None,
        evaluation: ProviderImageEvaluationResult | None,
    ) -> ImageResolutionResult:
        """Generate and materialize the fallback visual asset."""

        generation = await self.generation_provider.generate_image(
            prompt=prompt,
            metadata=metadata,
            reference_images=reference_images,
        )
        image = await self.materializer.materialize_generated(
            generation.image,
            label="generated_image",
        )

        return ImageResolutionResult(
            source="generated",
            image=image,
            generation=generation,
            evaluation=evaluation,
        )
