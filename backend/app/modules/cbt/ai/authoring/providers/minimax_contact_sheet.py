"""MiniMax evaluation adapter for numbered CBT candidate contact sheets."""

from __future__ import annotations

from typing import Any, Sequence

from app.modules.cbt.ai.authoring.image_contact_sheet import contact_sheet_candidate_count
from app.modules.cbt.ai.authoring.providers.base import (
    ProviderImageEvaluationResult,
    ProviderImageInput,
)
from app.modules.cbt.ai.authoring.providers.minimax import (
    MiniMaxImageEvaluationProvider,
    MiniMaxProviderError,
)


class MiniMaxContactSheetImageEvaluationProvider(MiniMaxImageEvaluationProvider):
    """Let MiniMax choose among many candidates shown inside one composite image."""

    supports_contact_sheet_selection = True

    async def evaluate_images(
        self,
        *,
        requirement: str,
        images: Sequence[ProviderImageInput],
    ) -> ProviderImageEvaluationResult:
        candidate_count = contact_sheet_candidate_count(images)
        if candidate_count is None:
            return await super().evaluate_images(requirement=requirement, images=images)

        normalized_requirement = requirement.strip()
        if not normalized_requirement:
            raise ValueError("Image requirement cannot be empty.")

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Evaluate the numbered candidate contact sheet for this CBT visual requirement:\n"
                    f"{normalized_requirement}\n\n"
                    f"The sheet contains candidates #0 through #{candidate_count - 1}. "
                    "Compare all visible candidates before deciding. Choose the single candidate "
                    "that most clearly satisfies the requirement. If none are suitable, choose "
                    "generation. Return JSON only as "
                    '{"decision":"use_candidate|generate_image","selected_index":0,'
                    '"reason":"short reason"}. selected_index must be the exact number printed '
                    "on the chosen tile. When generating, selected_index must be null."
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": self._data_uri(images[0]), "detail": "default"},
            },
        ]

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an image suitability judge for educational CBT questions. "
                        "Judge only the visible numbered candidates against the supplied requirement."
                    ),
                },
                {"role": "user", "content": content},
            ],
            "max_tokens": min(self.max_output_tokens, 256),
            "stream": False,
            "thinking": {"type": "disabled"},
        }

        response = await self._post(
            url=self._build_text_url(), payload=payload, timeout=self.timeout
        )
        result = self._parse_json_text(self._extract_text(response))
        decision = result.get("decision")
        selected_index = result.get("selected_index")
        reason = result.get("reason")

        if decision not in {"use_candidate", "generate_image"}:
            raise MiniMaxProviderError("MiniMax returned an invalid image evaluation decision.")
        if decision == "use_candidate":
            if type(selected_index) is not int or not 0 <= selected_index < candidate_count:
                raise MiniMaxProviderError(
                    "MiniMax selected an invalid contact-sheet candidate index."
                )
        else:
            selected_index = None

        return ProviderImageEvaluationResult(
            decision=decision,
            selected_index=selected_index,
            reason=reason.strip() if isinstance(reason, str) and reason.strip() else None,
            usage=self._extract_usage(response),
            raw_response=response,
        )
