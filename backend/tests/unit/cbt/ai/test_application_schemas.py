from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.cbt.ai.schemas import (
    AIGenerateQuestionsRequest,
    AIRegenerateQuestionRequest,
)


def test_generation_schema_accepts_exact_question_type_distribution() -> None:
    payload = AIGenerateQuestionsRequest(
        subject="Mathematics",
        academic_level="SS2",
        topics=["Algebra", "Geometry"],
        question_count=5,
        question_type_counts={
            "single_choice": 3,
            "multiple_choice": 2,
        },
        visual_mode="auto",
    )

    assert payload.question_count == 5
    assert payload.question_type_counts == {
        "single_choice": 3,
        "multiple_choice": 2,
    }


def test_generation_schema_rejects_distribution_that_does_not_match_count() -> None:
    with pytest.raises(ValidationError, match="must sum to question_count"):
        AIGenerateQuestionsRequest(
            subject="Mathematics",
            academic_level="SS2",
            topics=["Algebra"],
            question_count=5,
            question_type_counts={"single_choice": 4},
        )


def test_generation_schema_rejects_duplicate_topics_case_insensitively() -> None:
    with pytest.raises(ValidationError, match="topics must be unique"):
        AIGenerateQuestionsRequest(
            subject="Mathematics",
            academic_level="SS2",
            topics=["Algebra", " algebra "],
            question_count=2,
        )


def test_regeneration_schema_validates_existing_question_correct_answers() -> None:
    with pytest.raises(ValidationError, match="exactly one correct option"):
        AIRegenerateQuestionRequest(
            subject="Mathematics",
            academic_level="SS2",
            topics=["Algebra"],
            existing_question={
                "question_type": "single_choice",
                "prompt": "Which is correct?",
                "options": [
                    {"text": "A", "is_correct": True},
                    {"text": "B", "is_correct": True},
                ],
            },
            instruction="Rewrite this question",
        )


def test_regeneration_schema_accepts_valid_question() -> None:
    payload = AIRegenerateQuestionRequest(
        subject="Biology",
        academic_level="SS1",
        topics=["Cells"],
        existing_question={
            "question_type": "single_choice",
            "prompt": "What is the basic unit of life?",
            "options": [
                {"text": "Cell", "is_correct": True},
                {"text": "Tissue", "is_correct": False},
            ],
        },
        instruction="Make the wording less obvious",
        visual_mode="text_only",
    )

    assert payload.existing_question.question_type == "single_choice"
    assert payload.visual_mode == "text_only"
