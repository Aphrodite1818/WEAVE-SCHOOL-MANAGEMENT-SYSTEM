from __future__ import annotations

# ==========================#
#    PROVIDER FACTORY      #
# ==========================#

from typing import TYPE_CHECKING

from app.config.settings import settings

from app.modules.AI.providers.claude import ClaudeProvider
from app.modules.AI.providers.openai import OpenAIProvider
from app.modules.AI.providers.gemini import GeminiProvider
from app.config.logging import get_logger

if TYPE_CHECKING:
    from app.modules.AI.providers.base import BaseLLMProvider


logger = get_logger(__name__)


class ProviderFactory:
    """Factory for selecting AI providers."""

    @staticmethod
    def get_provider(provider_name: str) -> BaseLLMProvider:
        """Return the configured AI provider."""
        provider_name = provider_name.lower()

        providers = {
            "gemini": lambda: GeminiProvider(
                settings.GEMINI_API_KEY,
                settings.GEMINI_MODEL,
                settings.LLM_MAX_TOKENS,
            ),
            "claude": lambda: ClaudeProvider(
                settings.ANTHROPIC_API_KEY,
                settings.ANTHROPIC_MODEL,
                settings.LLM_MAX_TOKENS,
            ),
            "openai": lambda: OpenAIProvider(
                settings.OPENAI_API_KEY,
                settings.OPENAI_MODEL,
                settings.LLM_MAX_TOKENS,
            ),
        }

        factory = providers.get(provider_name)

        if not factory:
            logger.error(f"Provider not available: {provider_name}")
            raise ValueError(
                f"Unknown provider: '{provider_name}'. Available: {list(providers.keys())}"
            )

        logger.info(f"Returning provider: {provider_name}")
        return factory()
