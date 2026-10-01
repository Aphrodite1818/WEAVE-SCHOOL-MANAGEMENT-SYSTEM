from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.cbt.ai.schemas import (
    AIGenerateQuestionsRequest,
    AIRegenerateQuestionRequest,
)


def _existing_question() -> dict:
    return {
        "question_type": "single_choice",
        "prompt": "What is the basic unit of life?",
        "options": [
            {"text": "Cell", "is_correct": True},
            {"text": "Tissue", "is_correct": False},
        ],
    }


def test_generation_difficulty_defaults_to_medium() -> None:
    request = AIGenerateQuestionsRequest(
        subject="Biology",
        academic_level="SS1",
        generation_prompt="Generate questions about cells.",
        question_count=1,
        visual_mode="text_only",
    )

    assert request.difficulty == "medium"
    assert request.model_dump(exclude_none=True)["difficulty"] == "medium"


@pytest.mark.parametrize("difficulty", ["easy", "medium", "difficult"])
def test_generation_accepts_supported_difficulties(difficulty: str) -> None:
    request = AIGenerateQuestionsRequest(
        subject="Mathematics",
        academic_level="SS2",
        generation_prompt="Generate questions about algebra.",
        question_count=1,
        difficulty=difficulty,
        visual_mode="text_only",
    )

    assert request.difficulty == difficulty


def test_generation_rejects_unsupported_difficulty() -> None:
    with pytest.raises(ValidationError):
        AIGenerateQuestionsRequest(
            subject="Mathematics",
            academic_level="SS2",
            generation_prompt="Generate questions about algebra.",
            question_count=1,
            difficulty="expert",
            visual_mode="text_only",
        )


def test_regeneration_difficulty_defaults_to_medium() -> None:
    request = AIRegenerateQuestionRequest(
        subject="Biology",
        academic_level="SS1",
        generation_prompt="Keep the question focused on cells.",
        existing_question=_existing_question(),
        instruction="Rewrite the question",
        visual_mode="text_only",
    )

    assert request.difficulty == "medium"
    assert request.model_dump(exclude_none=True)["difficulty"] == "medium"


def test_regeneration_accepts_difficult_difficulty() -> None:
    request = AIRegenerateQuestionRequest(
        subject="Biology",
        academic_level="SS1",
        generation_prompt="Keep the question focused on cells.",
        existing_question=_existing_question(),
        instruction="Require deeper application",
        difficulty="difficult",
        visual_mode="text_only",
    )

    assert request.difficulty == "difficult"
