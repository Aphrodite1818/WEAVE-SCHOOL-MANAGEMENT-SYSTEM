# ==========================#
#     BASE LLM PROVIDER    #
# ==========================#


"""Define the abstract interface implemented by all LLM providers."""

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Abstract base class for chat-capable LLM provider integrations."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],  # e.g dict{"role" : "user" , "content" : "---"}
        tools: (
            list[dict[str, Any]] | None
        ) = None,  # pass a list of tools dict{"academic":academic()} | None
    ) -> dict[str, Any]:  # must return a dictionary
        """
        Send messages to LLM provider.

        Returns standardized response:
        {
            "content": str,
            "tool_calls": list | None,
            "raw_response": Any
        }
        """
        raise NotImplementedError
