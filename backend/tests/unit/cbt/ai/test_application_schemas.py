from __future__ import annotations

import base64
import hashlib
from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError

from app.modules.cbt.ai.schemas import (
    AIGenerateQuestionsRequest,
    AIImageTransportPayload,
    AIRegenerateQuestionRequest,
)


def _png_transport() -> dict[str, str]:
    buffer = BytesIO()
    Image.new("RGB", (8, 6), "white").save(buffer, format="PNG")
    raw = buffer.getvalue()
    return {
        "content_type": "image/png",
        "data_base64": base64.b64encode(raw).decode("ascii"),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def test_generation_schema_accepts_exact_question_type_distribution() -> None:
    payload = AIGenerateQuestionsRequest(
        subject="Mathematics",
        academic_level="SS2",
        topics=["Algebra", "Geometry"],
        question_count=5,
        question_type_counts={"single_choice": 3, "multiple_choice": 2},
        visual_mode="auto",
    )
    assert payload.question_count == 5
    assert payload.question_type_counts == {
        "single_choice": 3,
        "multiple_choice": 2,
    }


def test_generation_schema_accepts_fifty_questions() -> None:
    payload = AIGenerateQuestionsRequest(
        subject="Chemistry",
        academic_level="JSS1",
        topics=["Atoms"],
        question_count=50,
        question_type_counts={"single_choice": 50, "multiple_choice": 0},
        visual_mode="text_only",
    )
    assert payload.question_count == 50


def test_generation_schema_rejects_more_than_fifty_questions() -> None:
    with pytest.raises(ValidationError):
        AIGenerateQuestionsRequest(
            subject="Chemistry",
            academic_level="JSS1",
            topics=["Atoms"],
            question_count=51,
            question_type_counts={"single_choice": 51, "multiple_choice": 0},
            visual_mode="text_only",
        )


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


def test_image_transport_accepts_valid_encoded_file_bytes() -> None:
    transport = _png_transport()
    payload = AIImageTransportPayload(**transport)
    assert payload.content_type == "image/png"
    assert base64.b64decode(payload.data_base64).startswith(b"\x89PNG\r\n\x1a\n")


def test_image_transport_rejects_hash_mismatch() -> None:
    transport = _png_transport()
    transport["sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="SHA-256"):
        AIImageTransportPayload(**transport)


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


def test_regeneration_schema_accepts_question_and_option_images() -> None:
    image = _png_transport()
    payload = AIRegenerateQuestionRequest(
        subject="Biology",
        academic_level="SS1",
        topics=["Cells"],
        existing_question={
            "question_type": "single_choice",
            "prompt": "Identify the structure shown.",
            "image": image,
            "options": [
                {"text": None, "image": image, "is_correct": True},
                {"text": "Mitochondrion", "is_correct": False},
            ],
        },
        instruction="Make the question harder",
        visual_mode="auto",
    )
    assert payload.existing_question.image is not None
    assert payload.existing_question.options[0].image is not None


def test_regeneration_schema_rejects_duplicate_topics() -> None:
    with pytest.raises(ValidationError, match="topics must be unique"):
        AIRegenerateQuestionRequest(
            subject="Biology",
            academic_level="SS1",
            topics=["Cells", " cells "],
            existing_question={
                "question_type": "single_choice",
                "prompt": "What is the basic unit of life?",
                "options": [
                    {"text": "Cell", "is_correct": True},
                    {"text": "Tissue", "is_correct": False},
                ],
            },
            instruction="Rewrite this question",
        )


def test_regeneration_schema_accepts_valid_text_only_question() -> None:
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
