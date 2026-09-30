"""Question-authoring orchestration for CBT AI."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from app.modules.cbt.ai.image_resolver import ImageResolver
from app.modules.cbt.ai.providers.base import (
    BaseQuestionGenerationProvider,
    ImageResolutionResult,
    ProviderQuestionGenerationResult,
    ProviderUsage,
)
from app.modules.cbt.ai.schemas import (
    AIQuestionDraft,
    AIVisualMode,
)
from app.modules.cbt.ai.validation import (
    AIResponseValidationError,
    SUPPORTED_VISUAL_MODES,
    validate_generated_question_batch,
    validate_regenerated_question,
)


QuestionType = Literal[
    "single_choice",
    "multiple_choice",
]

AuthoringOperation = Literal[
    "generation",
    "regeneration",
]

DEFAULT_VISUAL_MODE: AIVisualMode = "auto"


@dataclass(slots=True)
class AuthoredQuestion:
    """
    One trusted CBT question together with any resolved visual assets.

    The original AIImageDirective remains inside the validated question.
    Resolved image results are carried separately so provider/search
    details do not contaminate the question schema.
    """

    question: AIQuestionDraft

    question_image: ImageResolutionResult | None = None

    option_images: dict[int, ImageResolutionResult] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class QuestionGenerationResult:
    """Complete result returned after authoring a question batch."""

    questions: list[AuthoredQuestion]
    usage: ProviderUsage
    repaired: bool = False


@dataclass(slots=True)
class QuestionRegenerationResult:
    """Complete result returned after re-authoring one question."""

    question: AuthoredQuestion
    usage: ProviderUsage
    repaired: bool = False


class QuestionAuthoringService:
    """
    Coordinate CBT question authoring.

    Responsibilities:

    - normalize the visual authoring policy
    - generate question drafts
    - regenerate one question
    - validate provider output
    - perform at most one internal repair attempt
    - resolve question-level image directives
    - resolve option-level image directives
    - aggregate provider usage
    - return trusted authored questions

    This service does not handle authentication, authorization,
    quotas, billing, payments, tenant access, or HTTP concerns.
    """

    def __init__(
        self,
        *,
        question_provider: BaseQuestionGenerationProvider,
        image_resolver: ImageResolver,
    ) -> None:
        self.question_provider = question_provider
        self.image_resolver = image_resolver

    async def generate_questions(
        self,
        *,
        request: Mapping[str, Any],
        expected_count: int | None = None,
        expected_type_counts: Mapping[str, int] | None = None,
    ) -> QuestionGenerationResult:
        """
        Generate a trusted, fully authored batch of CBT questions.

        Invalid question output receives exactly one repair attempt.
        Images are resolved only after the final question batch passes
        validation.
        """

        request_payload, visual_mode = self._prepare_authoring_request(
            request
        )

        provider_result = (
            await self.question_provider.generate_questions(
                request=request_payload,
            )
        )

        repaired = False
        question_usage = provider_result.usage

        try:
            questions = validate_generated_question_batch(
                provider_result.questions,
                expected_count=expected_count,
                expected_type_counts=expected_type_counts,
                visual_mode=visual_mode,
            )

        except AIResponseValidationError as validation_error:
            repaired_result = await self._repair_questions(
                original_request=request_payload,
                invalid_questions=provider_result.questions,
                validation_error=validation_error,
                operation="generation",
            )

            # Exactly one repair attempt.
            # If this fails, AIResponseValidationError propagates.
            questions = validate_generated_question_batch(
                repaired_result.questions,
                expected_count=expected_count,
                expected_type_counts=expected_type_counts,
                visual_mode=visual_mode,
            )

            question_usage = self._combine_usage(
                provider_result.usage,
                repaired_result.usage,
            )

            repaired = True

        authored_questions: list[AuthoredQuestion] = []
        image_usages: list[ProviderUsage] = []

        for question in questions:
            authored_question, usages = (
                await self._resolve_question_images(
                    question
                )
            )

            authored_questions.append(
                authored_question
            )

            image_usages.extend(usages)

        total_usage = self._combine_usage(
            question_usage,
            *image_usages,
        )

        return QuestionGenerationResult(
            questions=authored_questions,
            usage=total_usage,
            repaired=repaired,
        )

    async def regenerate_question(
        self,
        *,
        request: Mapping[str, Any],
        expected_question_type: QuestionType | None = None,
    ) -> QuestionRegenerationResult:
        """
        Regenerate one trusted, fully authored CBT question.

        Invalid output receives exactly one repair attempt before image
        resolution occurs.
        """

        request_payload, visual_mode = self._prepare_authoring_request(
            request
        )

        provider_result = (
            await self.question_provider.regenerate_question(
                request=request_payload,
            )
        )

        repaired = False
        question_usage = provider_result.usage

        try:
            question = validate_regenerated_question(
                provider_result.question,
                expected_question_type=expected_question_type,
                visual_mode=visual_mode,
            )

        except AIResponseValidationError as validation_error:
            repaired_result = await self._repair_questions(
                original_request=request_payload,
                invalid_questions=[
                    provider_result.question,
                ],
                validation_error=validation_error,
                operation="regeneration",
            )

            repaired_questions = (
                validate_generated_question_batch(
                    repaired_result.questions,
                    expected_count=1,
                    expected_type_counts=(
                        self._single_question_type_counts(
                            expected_question_type
                        )
                    ),
                    visual_mode=visual_mode,
                )
            )

            question = validate_regenerated_question(
                repaired_questions[0],
                expected_question_type=expected_question_type,
                visual_mode=visual_mode,
            )

            question_usage = self._combine_usage(
                provider_result.usage,
                repaired_result.usage,
            )

            repaired = True

        authored_question, image_usages = (
            await self._resolve_question_images(
                question
            )
        )

        total_usage = self._combine_usage(
            question_usage,
            *image_usages,
        )

        return QuestionRegenerationResult(
            question=authored_question,
            usage=total_usage,
            repaired=repaired,
        )

    async def _repair_questions(
        self,
        *,
        original_request: Mapping[str, Any],
        invalid_questions: list[dict[str, Any]],
        validation_error: AIResponseValidationError,
        operation: AuthoringOperation,
    ) -> ProviderQuestionGenerationResult:
        """
        Perform one provider repair request.

        Retry policy belongs here rather than inside the concrete
        provider implementation.
        """

        repair_request = self._build_repair_request(
            original_request=original_request,
            invalid_questions=invalid_questions,
            validation_error=validation_error,
            operation=operation,
        )

        return await self.question_provider.repair_questions(
            request=repair_request,
        )

    async def _resolve_question_images(
        self,
        question: AIQuestionDraft,
    ) -> tuple[
        AuthoredQuestion,
        list[ProviderUsage],
    ]:
        """
        Resolve every image directive belonging to one trusted question.

        Images may occur on:

        - the question itself
        - individual answer options

        ImageResolver decides whether to use a searched image or fall
        back to image generation.
        """

        question_image: ImageResolutionResult | None = None

        option_images: dict[
            int,
            ImageResolutionResult,
        ] = {}

        usages: list[ProviderUsage] = []

        if question.image is not None:
            question_image = await self.image_resolver.resolve(
                requirement=question.image.requirement,
                search_query=question.image.search_query,
                generation_prompt=(
                    question.image.generation_prompt
                ),
            )

            usages.extend(
                self._image_resolution_usages(
                    question_image
                )
            )

        for index, option in enumerate(question.options):
            if option.image is None:
                continue

            resolution = await self.image_resolver.resolve(
                requirement=option.image.requirement,
                search_query=option.image.search_query,
                generation_prompt=(
                    option.image.generation_prompt
                ),
            )

            option_images[index] = resolution

            usages.extend(
                self._image_resolution_usages(
                    resolution
                )
            )

        return (
            AuthoredQuestion(
                question=question,
                question_image=question_image,
                option_images=option_images,
            ),
            usages,
        )

    @staticmethod
    def _image_resolution_usages(
        resolution: ImageResolutionResult,
    ) -> list[ProviderUsage]:
        """
        Extract billable/model usage from one image-resolution operation.

        Search itself currently has no ProviderUsage.
        Evaluation consumes model usage when candidates are reviewed.
        Generation consumes provider usage when a generated fallback
        image is required.
        """

        usages: list[ProviderUsage] = []

        if resolution.evaluation is not None:
            usages.append(
                resolution.evaluation.usage
            )

        if resolution.generation is not None:
            usages.append(
                resolution.generation.usage
            )

        return usages

    @staticmethod
    def _prepare_authoring_request(
        request: Mapping[str, Any],
    ) -> tuple[dict[str, Any], AIVisualMode]:
        """
        Normalize the provider request and make visual policy explicit.

        Until the router-facing request schema is introduced, omitted
        visual_mode defaults to `auto`. Invalid modes fail before a
        provider call is made.
        """

        request_payload = dict(request)
        raw_visual_mode = request_payload.get(
            "visual_mode",
            DEFAULT_VISUAL_MODE,
        )

        if raw_visual_mode not in SUPPORTED_VISUAL_MODES:
            raise ValueError(
                f"Unsupported visual mode: {raw_visual_mode!r}."
            )

        visual_mode = cast(
            AIVisualMode,
            raw_visual_mode,
        )

        request_payload["visual_mode"] = visual_mode

        return request_payload, visual_mode

    @staticmethod
    def _build_repair_request(
        *,
        original_request: Mapping[str, Any],
        invalid_questions: list[dict[str, Any]],
        validation_error: AIResponseValidationError,
        operation: AuthoringOperation,
    ) -> dict[str, Any]:
        """Build provider-neutral input for one repair attempt."""

        return {
            "operation": operation,
            "original_request": dict(
                original_request
            ),
            "invalid_questions": invalid_questions,
            "validation_feedback": (
                validation_error.to_repair_feedback()
            ),
        }

    @staticmethod
    def _single_question_type_counts(
        expected_question_type: QuestionType | None,
    ) -> dict[str, int] | None:
        """Build expected type distribution for repaired regeneration."""

        if expected_question_type is None:
            return None

        return {
            expected_question_type: 1,
        }

    @staticmethod
    def _combine_usage(
        *usages: ProviderUsage,
    ) -> ProviderUsage:
        """
        Aggregate usage across the complete authoring operation.

        This can include:

        - initial question generation
        - question repair
        - image evaluation
        - fallback image generation
        """

        input_tokens = sum(
            usage.input_tokens
            for usage in usages
        )

        output_tokens = sum(
            usage.output_tokens
            for usage in usages
        )

        cache_read_tokens = sum(
            usage.cache_read_tokens
            for usage in usages
        )

        provider_cost: float | None = None
        currency: str | None = None

        cost_usages = [
            usage
            for usage in usages
            if usage.provider_cost is not None
        ]

        if cost_usages:
            currencies = {
                usage.currency
                for usage in cost_usages
            }

            if len(currencies) == 1:
                currency = next(
                    iter(currencies)
                )

                provider_cost = sum(
                    usage.provider_cost or 0
                    for usage in cost_usages
                )

        return ProviderUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            provider_cost=provider_cost,
            currency=currency,
        )
