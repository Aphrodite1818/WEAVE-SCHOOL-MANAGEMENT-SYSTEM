"""Provider factory for CBT AI question authoring."""

from __future__ import annotations

from app.config.settings import settings
from app.modules.cbt.ai.authoring.image_resolver import ImageResolver
from app.modules.cbt.ai.authoring.providers.base import (
    BaseImageEvaluationProvider,
    BaseImageGenerationProvider,
    BaseImageSearchProvider,
    BaseQuestionGenerationProvider,
)
from app.modules.cbt.ai.authoring.providers.gemini import (
    GeminiImageEvaluationProvider,
    GeminiImageGenerationProvider,
    GeminiQuestionGenerationProvider,
)
from app.modules.cbt.ai.authoring.providers.minimax import (
    MiniMaxImageEvaluationProvider,
    MiniMaxImageGenerationProvider,
    MiniMaxQuestionGenerationProvider,
)
from app.modules.cbt.ai.authoring.providers.openverse import OpenverseImageSearchProvider


class CBTProviderFactoryError(RuntimeError):
    """Raised when a configured CBT AI provider is unsupported."""


class CBTProviderFactory:
    """Build the configured providers used by CBT AI authoring."""

    @staticmethod
    def get_question_provider() -> BaseQuestionGenerationProvider:
        provider = settings.CBT_AI_QUESTION_PROVIDER
        if provider == "gemini":
            return GeminiQuestionGenerationProvider()
        if provider == "minimax":
            return MiniMaxQuestionGenerationProvider()
        raise CBTProviderFactoryError(
            f"Unsupported CBT AI question provider: {provider!r}"
        )

    @staticmethod
    def get_image_evaluation_provider() -> BaseImageEvaluationProvider:
        provider = settings.CBT_AI_QUESTION_PROVIDER
        if provider == "gemini":
            return GeminiImageEvaluationProvider()
        if provider == "minimax":
            return MiniMaxImageEvaluationProvider()
        raise CBTProviderFactoryError(
            f"Unsupported CBT AI image evaluation provider: {provider!r}"
        )

    @staticmethod
    def get_image_generation_provider() -> BaseImageGenerationProvider:
        provider = settings.CBT_AI_IMAGE_PROVIDER
        if provider == "gemini":
            return GeminiImageGenerationProvider()
        if provider == "minimax":
            return MiniMaxImageGenerationProvider()
        raise CBTProviderFactoryError(
            f"Unsupported CBT AI image generation provider: {provider!r}"
        )

    @staticmethod
    def get_image_search_provider() -> BaseImageSearchProvider:
        provider = settings.CBT_AI_IMAGE_SEARCH_PROVIDER
        if provider == "openverse":
            return OpenverseImageSearchProvider()
        raise CBTProviderFactoryError(
            f"Unsupported CBT AI image search provider: {provider!r}"
        )

    @classmethod
    def get_image_resolver(cls) -> ImageResolver:
        return ImageResolver(
            search_provider=cls.get_image_search_provider(),
            evaluation_provider=cls.get_image_evaluation_provider(),
            generation_provider=cls.get_image_generation_provider(),
        )
