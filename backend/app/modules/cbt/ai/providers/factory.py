"""Provider factory for CBT AI question authoring"""

from __future__ import annotations

from app.config.settings import settings
from app.modules.cbt.ai.image_resolver import ImageResolver
from app.modules.cbt.ai.providers.base import (
    BaseImageEvaluationProvider,
    BaseImageSearchProvider,
    BaseImageGenerationProvider,
    BaseQuestionGenerationProvider,
)


from app.modules.cbt.ai.providers.gemini import (
    GeminiImageEvaluationProvider,
    GeminiImageGenerationProvider,
    GeminiQuestionGenerationProvider,
)

from app.modules.cbt.ai.providers.minimax import (
    MiniMaxImageEvaluationProvider,
    MiniMaxImageGenerationProvider,
    MiniMaxQuestionGenerationProvider,
)
from app.modules.cbt.ai.providers.openverse import (
    OpenverseImageSearchProvider,
)


class CBTProviderFactoryError(RuntimeError):
    """Raised when a configured CBT AI provider is unsupported"""


class CBTProviderFactory:
    """
    Build the configured providers used by CBT AI authoring

    Provider selection is centralized here so the rest of the CBT AI
    domain depends only on provider contracts rather than concrete
    Gemini, MiniMax or Openverse implementations
    """

    @staticmethod
    def get_question_provider() -> BaseQuestionGenerationProvider:
        """Return the configured question-generation provider"""

        provider = settings.CBT_AI_QUESTION_PROVIDER

        if provider == "gemini":
            return GeminiQuestionGenerationProvider()

        if provider == "minimax":
            return MiniMaxQuestionGenerationProvider()

        raise CBTProviderFactoryError(f"Unsupported CBT AI question provider: {provider!r}")

    @staticmethod
    def get_image_evaluation_provider() -> BaseImageEvaluationProvider:
        """
        Return the vision provider used to judge retrieved images.

        Image evaluation intentionally follows the active question provider.
        Therefore if Gemini generated the questions, Gemini evaluates the
        Openverse candidates. If MiniMax generated them, MiniMax evaluates
        the candidates.
        """

        provider = settings.CBT_AI_QUESTION_PROVIDER

        if provider == "gemini":
            return GeminiImageEvaluationProvider()

        if provider == "minimax":
            return MiniMaxImageEvaluationProvider()

        raise CBTProviderFactoryError(f"Unsupported CBT AI image evaluation provider: {provider!r}")

    @staticmethod
    def get_image_generation_provider() -> BaseImageGenerationProvider:
        """Return the configured image-generation provider."""

        provider = settings.CBT_AI_IMAGE_PROVIDER

        if provider == "gemini":
            return GeminiImageGenerationProvider()

        if provider == "minimax":
            return MiniMaxImageGenerationProvider()

        raise CBTProviderFactoryError(f"Unsupported CBT AI image generation provider: {provider!r}")

    @staticmethod
    def get_image_search_provider() -> BaseImageSearchProvider:
        """Return the configured image-search provider."""

        provider = settings.CBT_AI_IMAGE_SEARCH_PROVIDER

        if provider == "openverse":
            return OpenverseImageSearchProvider()

        raise CBTProviderFactoryError(f"Unsupported CBT AI image search provider: {provider!r}")

    @classmethod
    def get_image_resolver(cls) -> ImageResolver:
        """
        Build the complete provider-agnostic image resolution engine


        Flow:
            image search
            -> image evaluation
            -> selected search candidate
               OR
            ->image generation fallback
        """

        return ImageResolver(
            search_provider=cls.get_image_search_provider(),
            evaluation_provider=cls.get_image_evaluation_provider(),
            generation_provider=cls.get_image_generation_provider(),
        )
