from __future__ import annotations

import pytest

from app.modules.cbt.ai.authoring.contracts import (
    build_question_generation_prompt,
    build_question_regeneration_prompt,
    build_question_repair_prompt,
)
from app.modules.cbt.ai.authoring.service import QuestionAuthoringService


def test_authoring_request_defaults_difficulty_to_medium() -> None:
    payload, _ = QuestionAuthoringService._prepare_authoring_request(
        {"visual_mode": "text_only"}
    )

    assert payload["difficulty"] == "medium"


@pytest.mark.parametrize("difficulty", ["easy", "medium", "difficult"])
def test_authoring_request_preserves_supported_difficulty(difficulty: str) -> None:
    payload, _ = QuestionAuthoringService._prepare_authoring_request(
        {"difficulty": difficulty, "visual_mode": "text_only"}
    )

    assert payload["difficulty"] == difficulty


def test_authoring_request_rejects_unsupported_difficulty_before_provider_use() -> None:
    with pytest.raises(ValueError, match="Unsupported question difficulty"):
        QuestionAuthoringService._prepare_authoring_request(
            {"difficulty": "expert", "visual_mode": "text_only"}
        )


def test_generation_prompt_defines_difficulty_as_level_relative_cognitive_demand() -> None:
    prompt = build_question_generation_prompt()

    assert '`easy`, `medium`, or `difficult`' in prompt
    assert "relative to the supplied academic_level" in prompt
    assert "cognitive demand and application" in prompt
    assert "material beyond the requested level" in prompt


def test_regeneration_prompt_requires_requested_difficulty() -> None:
    prompt = build_question_regeneration_prompt()

    assert "Rewrite the question to the requested difficulty" in prompt
    assert "within the supplied academic_level and topic scope" in prompt


def test_repair_prompt_preserves_original_difficulty() -> None:
    prompt = build_question_repair_prompt()

    assert "original_request.difficulty" in prompt
    assert "including its difficulty and visual_mode policy" in prompt
