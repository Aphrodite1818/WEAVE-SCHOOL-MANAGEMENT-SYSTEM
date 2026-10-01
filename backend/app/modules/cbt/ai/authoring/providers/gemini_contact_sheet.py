"""Gemini evaluation adapter for numbered CBT candidate contact sheets."""

from __future__ import annotations

from typing import Any, Sequence

from app.modules.cbt.ai.authoring.image_contact_sheet import contact_sheet_candidate_count
from app.modules.cbt.ai.authoring.providers.base import (
    ProviderImageEvaluationResult,
    ProviderImageInput,
)
from app.modules.cbt.ai.authoring.providers.gemini import (
    GeminiImageEvaluationProvider,
    GeminiProviderError,
)


class GeminiContactSheetImageEvaluationProvider(GeminiImageEvaluationProvider):
    """Let Gemini choose among many candidates shown inside one composite image."""

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

        parts: list[dict[str, Any]] = [
            {
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
                )
            },
            self._image_part(images[0]),
        ]

        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are an image suitability judge for educational CBT questions. "
                            "Judge only the visible numbered candidates against the supplied requirement."
                        )
                    }
                ]
            },
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": min(self.max_output_tokens, 256),
            },
        }

        response = await self._post(model=self.model, payload=payload, timeout=self.timeout)
        result = self._parse_json_text(self._extract_text(response))
        decision = result.get("decision")
        selected_index = result.get("selected_index")
        reason = result.get("reason")

        if decision not in {"use_candidate", "generate_image"}:
            raise GeminiProviderError("Gemini returned an invalid image evaluation decision.")
        if decision == "use_candidate":
            if type(selected_index) is not int or not 0 <= selected_index < candidate_count:
                raise GeminiProviderError("Gemini selected an invalid contact-sheet candidate index.")
        else:
            selected_index = None

        return ProviderImageEvaluationResult(
            decision=decision,
            selected_index=selected_index,
            reason=reason.strip() if isinstance(reason, str) and reason.strip() else None,
            usage=self._extract_usage(response),
            raw_response=response,
        )
