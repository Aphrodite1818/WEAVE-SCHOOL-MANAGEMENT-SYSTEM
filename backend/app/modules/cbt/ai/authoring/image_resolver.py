"""Provider-agnostic image resolution engine for CBT AI authoring."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.config.logging import get_logger
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
    ProviderImageGenerationResult,
    ProviderImageInput,
)

logger = get_logger(__name__)


class ImageResolverError(RuntimeError):
    """Raised when providers return an invalid image-resolution decision."""


def _provider_name(provider: object) -> str:
    """Return a stable provider label for diagnostic logs."""

    provider_name = getattr(provider, "provider_name", None)
    if isinstance(provider_name, str) and provider_name.strip():
        return provider_name.strip()
    return type(provider).__name__


def _exception_chain(exc: BaseException, *, limit: int = 5) -> list[str]:
    """Render a bounded exception chain without changing exception handling."""

    chain: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen and len(chain) < limit:
        seen.add(id(current))
        chain.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__
    return chain


class ImageResolver:
    """Resolve CBT visual requirements into fully materialized image bytes.

    URLs and provider Base64 are transient inputs only. If resolve() returns
    successfully, ImageResolutionResult.image contains validated encoded image
    file bytes that can be sent to CBT or another provider without performing
    another external download.
    """

    DEFAULT_SEARCH_LIMIT = 10
    DEFAULT_REVIEW_LIMIT = 3
    MAX_GENERATION_MATERIALIZATION_ATTEMPTS = 2

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

        logger.info(
            "cbt.ai.image_resolution.started",
            extra={
                "image_search_provider": _provider_name(self.search_provider),
                "image_evaluation_provider": _provider_name(self.evaluation_provider),
                "image_generation_provider": _provider_name(self.generation_provider),
                "image_search_query": normalized_search_query,
                "image_requirement": normalized_requirement,
                "image_search_limit": self.search_limit,
                "image_review_limit": self.review_limit,
            },
        )

        logger.debug(
            "cbt.ai.image_resolution.search.started",
            extra={
                "image_search_provider": _provider_name(self.search_provider),
                "image_search_query": normalized_search_query,
            },
        )
        try:
            candidates = await self.search_provider.search(
                query=normalized_search_query,
                limit=self.search_limit,
                metadata=search_metadata,
            )
        except Exception as exc:
            logger.exception(
                "cbt.ai.image_resolution.search.failed",
                extra={
                    "image_search_provider": _provider_name(self.search_provider),
                    "image_search_query": normalized_search_query,
                    "image_error_type": type(exc).__name__,
                    "image_error_message": str(exc),
                },
            )
            raise

        logger.info(
            "cbt.ai.image_resolution.search.completed",
            extra={
                "image_search_provider": _provider_name(self.search_provider),
                "image_search_query": normalized_search_query,
                "image_candidate_count": len(candidates),
            },
        )

        materialized_candidates = await self._materialize_review_candidates(candidates)

        logger.info(
            "cbt.ai.image_resolution.materialization.completed",
            extra={
                "image_search_query": normalized_search_query,
                "image_candidate_count": len(candidates),
                "image_materialized_candidate_count": len(materialized_candidates),
                "image_failed_candidate_count": len(candidates) - len(materialized_candidates),
            },
        )

        if not materialized_candidates:
            fallback_reason = (
                "search_returned_no_candidates"
                if not candidates
                else "all_search_candidates_failed_materialization"
            )
            logger.warning(
                "cbt.ai.image_resolution.fallback_to_generation",
                extra={
                    "image_fallback_reason": fallback_reason,
                    "image_search_query": normalized_search_query,
                    "image_candidate_count": len(candidates),
                    "image_generation_provider": _provider_name(self.generation_provider),
                },
            )
            return await self._generate(
                prompt=normalized_generation_prompt,
                metadata=generation_metadata,
                reference_images=reference_images,
                evaluation=None,
            )

        logger.info(
            "cbt.ai.image_resolution.evaluation.started",
            extra={
                "image_evaluation_provider": _provider_name(self.evaluation_provider),
                "image_search_query": normalized_search_query,
                "image_review_candidate_count": len(materialized_candidates),
            },
        )
        try:
            evaluation = await self.evaluation_provider.evaluate_images(
                requirement=normalized_requirement,
                images=[image for _, image in materialized_candidates],
            )
        except Exception as exc:
            logger.exception(
                "cbt.ai.image_resolution.evaluation.failed",
                extra={
                    "image_evaluation_provider": _provider_name(self.evaluation_provider),
                    "image_search_query": normalized_search_query,
                    "image_review_candidate_count": len(materialized_candidates),
                    "image_error_type": type(exc).__name__,
                    "image_error_message": str(exc),
                },
            )
            raise

        logger.info(
            "cbt.ai.image_resolution.evaluation.completed",
            extra={
                "image_evaluation_provider": _provider_name(self.evaluation_provider),
                "image_search_query": normalized_search_query,
                "image_evaluation_decision": evaluation.decision,
                "image_selected_index": evaluation.selected_index,
                "image_evaluation_reason": evaluation.reason,
            },
        )

        if evaluation.decision == "generate_image":
            logger.warning(
                "cbt.ai.image_resolution.fallback_to_generation",
                extra={
                    "image_fallback_reason": "evaluation_requested_generation",
                    "image_search_query": normalized_search_query,
                    "image_evaluation_reason": evaluation.reason,
                    "image_generation_provider": _provider_name(self.generation_provider),
                },
            )
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
        logger.info(
            "cbt.ai.image_resolution.search_candidate.selected",
            extra={
                "image_search_query": normalized_search_query,
                "image_selected_index": selected_index,
                "image_candidate_source": selected_candidate.source,
                "image_candidate_external_id": selected_candidate.external_id,
                "image_candidate_title": selected_candidate.title,
                "image_width": selected_image.width,
                "image_height": selected_image.height,
                "image_content_type": selected_image.content_type,
                "image_bytes": len(selected_image.data),
            },
        )
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
        """Collect up to review_limit downloadable/valid candidates in rank order."""

        materialized: list[tuple[ImageCandidate, ProviderImageInput]] = []
        for candidate_index, candidate in enumerate(candidates):
            if len(materialized) >= self.review_limit:
                break

            logger.debug(
                "cbt.ai.image_resolution.candidate_materialization.started",
                extra={
                    "image_candidate_index": candidate_index,
                    "image_candidate_source": candidate.source,
                    "image_candidate_external_id": candidate.external_id,
                    "image_candidate_title": candidate.title,
                },
            )
            try:
                image = await self.materializer.materialize_candidate(
                    candidate,
                    label=f"search_candidate_{len(materialized)}",
                )
            except ImageMaterializationError as exc:
                logger.debug(
                    "cbt.ai.image_resolution.candidate_materialization.failed",
                    extra={
                        "image_candidate_index": candidate_index,
                        "image_candidate_source": candidate.source,
                        "image_candidate_external_id": candidate.external_id,
                        "image_candidate_title": candidate.title,
                        "image_error_type": type(exc).__name__,
                        "image_error_message": str(exc),
                        "image_error_chain": _exception_chain(exc),
                    },
                )
                continue

            logger.debug(
                "cbt.ai.image_resolution.candidate_materialization.succeeded",
                extra={
                    "image_candidate_index": candidate_index,
                    "image_candidate_source": candidate.source,
                    "image_candidate_external_id": candidate.external_id,
                    "image_candidate_title": candidate.title,
                    "image_content_type": image.content_type,
                    "image_width": image.width,
                    "image_height": image.height,
                    "image_bytes": len(image.data),
                },
            )
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
        """Generate a fallback visual and retry once if its payload is unusable."""

        generation_attempts: list[ProviderImageGenerationResult] = []
        last_error: ImageMaterializationError | None = None

        for attempt_index in range(1, self.MAX_GENERATION_MATERIALIZATION_ATTEMPTS + 1):
            logger.info(
                "cbt.ai.image_resolution.generation.started",
                extra={
                    "image_generation_provider": _provider_name(self.generation_provider),
                    "image_generation_attempt": attempt_index,
                    "image_generation_max_attempts": self.MAX_GENERATION_MATERIALIZATION_ATTEMPTS,
                },
            )
            try:
                generation = await self.generation_provider.generate_image(
                    prompt=prompt,
                    metadata=metadata,
                    reference_images=reference_images,
                )
            except Exception as exc:
                logger.exception(
                    "cbt.ai.image_resolution.generation_provider.failed",
                    extra={
                        "image_generation_provider": _provider_name(self.generation_provider),
                        "image_generation_attempt": attempt_index,
                        "image_error_type": type(exc).__name__,
                        "image_error_message": str(exc),
                    },
                )
                raise

            generation_attempts.append(generation)

            logger.debug(
                "cbt.ai.image_resolution.generation_provider.completed",
                extra={
                    "image_generation_provider": _provider_name(self.generation_provider),
                    "image_generation_attempt": attempt_index,
                    "image_generation_has_base64": bool(generation.image.data_base64),
                    "image_generation_has_url": bool(generation.image.url),
                    "image_generation_content_type": generation.image.content_type,
                },
            )

            try:
                image = await self.materializer.materialize_generated(
                    generation.image,
                    label="generated_image",
                )
            except ImageMaterializationError as exc:
                last_error = exc
                logger.warning(
                    "cbt.ai.image_resolution.generated_materialization.failed",
                    extra={
                        "image_generation_provider": _provider_name(self.generation_provider),
                        "image_generation_attempt": attempt_index,
                        "image_error_type": type(exc).__name__,
                        "image_error_message": str(exc),
                        "image_error_chain": _exception_chain(exc),
                    },
                )
                continue

            logger.info(
                "cbt.ai.image_resolution.generation.completed",
                extra={
                    "image_generation_provider": _provider_name(self.generation_provider),
                    "image_generation_attempt": attempt_index,
                    "image_content_type": image.content_type,
                    "image_width": image.width,
                    "image_height": image.height,
                    "image_bytes": len(image.data),
                },
            )
            return ImageResolutionResult(
                source="generated",
                image=image,
                generation=generation,
                generation_attempts=generation_attempts,
                evaluation=evaluation,
            )

        raise ImageResolverError(
            "Image generation provider returned unusable image data after retry."
        ) from last_error
