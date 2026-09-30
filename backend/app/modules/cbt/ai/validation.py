"""Strict validation for untrusted CBT AI question output."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from app.modules.cbt.ai.schemas import (
    AIQuestionBatchDraft,
    AIQuestionDraft,
    AIRegeneratedQuestionDraft,
)


SUPPORTED_QUESTION_TYPES = frozenset(
    {
        "single_choice",
        "multiple_choice",
    }
)

MAX_REPAIR_ISSUES = 50


@dataclass(frozen=True, slots=True)
class AIValidationIssue:
    """One provider-output validation problem."""

    path: str
    code: str
    message: str


class AIResponseValidationError(ValueError):
    """
    Raised when AI-generated output violates the trusted CBT contract.

    The original provider response is intentionally not embedded in this
    exception because provider output may be large and should not be
    copied unnecessarily into logs or repair prompts.
    """

    def __init__(
        self,
        message: str,
        *,
        issues: Sequence[AIValidationIssue] | None = None,
    ) -> None:
        super().__init__(message)
        self.issues = tuple(issues or ())

    def to_repair_feedback(self) -> dict[str, Any]:
        """
        Return bounded structured feedback suitable for one repair attempt.
        """

        return {
            "error": "invalid_generated_questions",
            "message": str(self),
            "issues": [
                {
                    "path": issue.path,
                    "code": issue.code,
                    "message": issue.message,
                }
                for issue in self.issues[:MAX_REPAIR_ISSUES]
            ],
        }


def _format_location(
    location: Sequence[str | int],
) -> str:
    """Convert Pydantic error locations into readable dotted paths."""

    if not location:
        return "$"

    parts: list[str] = []

    for item in location:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
        else:
            parts.append(str(item))

    return ".".join(parts)


def _issues_from_pydantic(
    exc: ValidationError,
) -> list[AIValidationIssue]:
    """Normalize Pydantic validation errors for repair feedback."""

    issues: list[AIValidationIssue] = []

    for error in exc.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    ):
        location = error.get("loc") or ()
        message = str(error.get("msg") or "Invalid value.")
        code = str(error.get("type") or "validation_error")

        issues.append(
            AIValidationIssue(
                path=_format_location(location),
                code=code,
                message=message,
            )
        )

    return issues


def _normalized_text(value: str) -> str:
    """Normalize human-readable text for duplicate detection."""

    return " ".join(value.split()).casefold()


def _question_fingerprint(
    question: AIQuestionDraft,
) -> tuple[Any, ...]:
    """
    Build a semantic fingerprint used to reject duplicate generated questions.

    Correct-answer flags are intentionally included because two otherwise
    identical prompts/options with different answer keys must not silently
    collapse into the same identity.
    """

    option_fingerprints: list[tuple[Any, ...]] = []

    for option in question.options:
        image_fingerprint = None

        if option.image is not None:
            image_fingerprint = (
                _normalized_text(
                    option.image.requirement
                ),
                _normalized_text(
                    option.image.search_query
                ),
            )

        option_fingerprints.append(
            (
                _normalized_text(option.text)
                if option.text
                else None,
                image_fingerprint,
                option.is_correct,
            )
        )

    question_image = None

    if question.image is not None:
        question_image = (
            _normalized_text(
                question.image.requirement
            ),
            _normalized_text(
                question.image.search_query
            ),
        )

    return (
        question.question_type,
        _normalized_text(question.prompt),
        question_image,
        tuple(option_fingerprints),
    )


def _validate_expected_count(
    questions: Sequence[AIQuestionDraft],
    *,
    expected_count: int | None,
) -> list[AIValidationIssue]:
    issues: list[AIValidationIssue] = []

    if expected_count is None:
        return issues

    if type(expected_count) is not int or expected_count <= 0:
        raise ValueError(
            "expected_count must be a positive integer."
        )

    actual_count = len(questions)

    if actual_count != expected_count:
        issues.append(
            AIValidationIssue(
                path="questions",
                code="question_count_mismatch",
                message=(
                    f"Expected exactly {expected_count} questions "
                    f"but provider returned {actual_count}."
                ),
            )
        )

    return issues


def _validate_expected_type_counts(
    questions: Sequence[AIQuestionDraft],
    *,
    expected_type_counts: Mapping[str, int] | None,
) -> list[AIValidationIssue]:
    issues: list[AIValidationIssue] = []

    if expected_type_counts is None:
        return issues

    normalized_expected: dict[str, int] = {}

    for question_type, count in expected_type_counts.items():
        if question_type not in SUPPORTED_QUESTION_TYPES:
            raise ValueError(
                f"Unsupported expected question type: "
                f"{question_type!r}."
            )

        if type(count) is not int or count < 0:
            raise ValueError(
                "Expected question-type counts must be "
                "non-negative integers."
            )

        normalized_expected[question_type] = count

    actual_counts = Counter(
        question.question_type
        for question in questions
    )

    for question_type in SUPPORTED_QUESTION_TYPES:
        expected = normalized_expected.get(
            question_type,
            0,
        )
        actual = actual_counts.get(
            question_type,
            0,
        )

        if actual != expected:
            issues.append(
                AIValidationIssue(
                    path="questions",
                    code="question_type_count_mismatch",
                    message=(
                        f"Expected {expected} "
                        f"{question_type} question(s) "
                        f"but provider returned {actual}."
                    ),
                )
            )

    return issues


def _validate_no_duplicate_questions(
    questions: Sequence[AIQuestionDraft],
) -> list[AIValidationIssue]:
    """Reject duplicate questions inside one generated batch."""

    issues: list[AIValidationIssue] = []
    seen: dict[tuple[Any, ...], int] = {}

    for index, question in enumerate(questions):
        fingerprint = _question_fingerprint(question)

        original_index = seen.get(fingerprint)

        if original_index is not None:
            issues.append(
                AIValidationIssue(
                    path=f"questions[{index}]",
                    code="duplicate_question",
                    message=(
                        "Generated question duplicates "
                        f"questions[{original_index}]."
                    ),
                )
            )
            continue

        seen[fingerprint] = index

    return issues


def validate_generated_question_batch(
    raw_questions: Sequence[Mapping[str, Any]],
    *,
    expected_count: int | None = None,
    expected_type_counts: Mapping[str, int] | None = None,
) -> list[AIQuestionDraft]:
    """
    Validate a provider-generated batch and return trusted question drafts.

    This function performs:

    1. strict structural validation
    2. per-question-type validation
    3. exact requested-count validation
    4. requested question-type count validation
    5. duplicate-question detection

    No question should be returned to the CBT server before passing here.
    """

    if isinstance(raw_questions, (str, bytes)):
        raise AIResponseValidationError(
            "AI question output must be an array of question objects.",
            issues=[
                AIValidationIssue(
                    path="questions",
                    code="invalid_questions_container",
                    message=(
                        "Expected an array of question objects."
                    ),
                )
            ],
        )

    if not isinstance(raw_questions, Sequence):
        raise AIResponseValidationError(
            "AI question output must be an array of question objects.",
            issues=[
                AIValidationIssue(
                    path="questions",
                    code="invalid_questions_container",
                    message=(
                        "Expected an array of question objects."
                    ),
                )
            ],
        )

    raw_list = list(raw_questions)

    try:
        batch = AIQuestionBatchDraft.model_validate(
            {
                "questions": raw_list,
            }
        )
    except ValidationError as exc:
        raise AIResponseValidationError(
            "AI-generated questions failed schema validation.",
            issues=_issues_from_pydantic(exc),
        ) from exc

    questions = list(batch.questions)

    issues: list[AIValidationIssue] = []

    issues.extend(
        _validate_expected_count(
            questions,
            expected_count=expected_count,
        )
    )

    issues.extend(
        _validate_expected_type_counts(
            questions,
            expected_type_counts=expected_type_counts,
        )
    )

    issues.extend(
        _validate_no_duplicate_questions(
            questions
        )
    )

    if issues:
        raise AIResponseValidationError(
            "AI-generated questions failed contract validation.",
            issues=issues,
        )

    return questions


def validate_regenerated_question(
    raw_question: Mapping[str, Any],
    *,
    expected_question_type: Literal[
        "single_choice",
        "multiple_choice",
    ]
    | None = None,
) -> AIQuestionDraft:
    """
    Validate one regenerated question.

    By default the provider may return either supported question type.

    When regeneration is intended to preserve the current question type,
    pass `expected_question_type`.
    """

    if not isinstance(raw_question, Mapping):
        raise AIResponseValidationError(
            "AI-regenerated question must be an object.",
            issues=[
                AIValidationIssue(
                    path="question",
                    code="invalid_question_container",
                    message="Expected a question object.",
                )
            ],
        )

    try:
        envelope = AIRegeneratedQuestionDraft.model_validate(
            {
                "question": dict(raw_question),
            }
        )
    except ValidationError as exc:
        raise AIResponseValidationError(
            "AI-regenerated question failed schema validation.",
            issues=_issues_from_pydantic(exc),
        ) from exc

    question = envelope.question

    if (
        expected_question_type is not None
        and question.question_type
        != expected_question_type
    ):
        raise AIResponseValidationError(
            "AI-regenerated question changed question type unexpectedly.",
            issues=[
                AIValidationIssue(
                    path="question.question_type",
                    code="question_type_changed",
                    message=(
                        f"Expected {expected_question_type!r} "
                        f"but provider returned "
                        f"{question.question_type!r}."
                    ),
                )
            ],
        )

    return question