"""Public application contracts for CBT AI routes."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.cbt.ai.authoring.schemas import AIVisualMode


AIQuestionType = Literal["single_choice", "multiple_choice"]

MAX_PUBLIC_TOPIC_COUNT = 50
MAX_PUBLIC_QUESTION_COUNT = 100
MAX_PUBLIC_TEXT_LENGTH = 20_000
MAX_PUBLIC_INSTRUCTION_LENGTH = 10_000


class CBTAISchemaBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class AIGenerateQuestionsRequest(CBTAISchemaBase):
    """Generate a validated batch of questions for one academic context."""

    subject: str = Field(min_length=1, max_length=200)
    academic_level: str = Field(min_length=1, max_length=200)
    topics: list[str] = Field(min_length=1, max_length=MAX_PUBLIC_TOPIC_COUNT)
    question_count: int = Field(ge=1, le=MAX_PUBLIC_QUESTION_COUNT)
    question_type_counts: dict[AIQuestionType, int] | None = None
    visual_mode: AIVisualMode = "auto"
    instructions: str | None = Field(default=None, max_length=MAX_PUBLIC_INSTRUCTION_LENGTH)
    context: str | None = Field(default=None, max_length=MAX_PUBLIC_TEXT_LENGTH)

    @model_validator(mode="after")
    def validate_generation_shape(self) -> Self:
        normalized_topics = [topic.strip() for topic in self.topics]
        if any(not topic for topic in normalized_topics):
            raise ValueError("topics cannot contain blank values")
        if len({topic.casefold() for topic in normalized_topics}) != len(normalized_topics):
            raise ValueError("topics must be unique")
        self.topics = normalized_topics

        if self.question_type_counts is not None:
            if any(
                type(count) is not int or count < 0
                for count in self.question_type_counts.values()
            ):
                raise ValueError("question_type_counts values must be non-negative integers")
            if sum(self.question_type_counts.values()) != self.question_count:
                raise ValueError("question_type_counts must sum to question_count")
        return self


class AIExistingQuestionOption(CBTAISchemaBase):
    text: str | None = Field(default=None, max_length=10_000)
    is_correct: bool

    @model_validator(mode="after")
    def require_content(self) -> Self:
        if not self.text:
            raise ValueError("Existing question options must contain text")
        return self


class AIExistingQuestion(CBTAISchemaBase):
    question_type: AIQuestionType
    prompt: str = Field(min_length=1, max_length=MAX_PUBLIC_TEXT_LENGTH)
    instruction: str | None = Field(default=None, max_length=MAX_PUBLIC_INSTRUCTION_LENGTH)
    options: list[AIExistingQuestionOption] = Field(min_length=2, max_length=50)

    @model_validator(mode="after")
    def validate_correct_answers(self) -> Self:
        correct_count = sum(1 for option in self.options if option.is_correct)
        if self.question_type == "single_choice" and correct_count != 1:
            raise ValueError("A single-choice question must have exactly one correct option")
        if self.question_type == "multiple_choice":
            if correct_count < 2:
                raise ValueError("A multiple-choice question must have at least two correct options")
            if correct_count == len(self.options):
                raise ValueError(
                    "A multiple-choice question must have at least one incorrect option"
                )
        return self


class AIRegenerateQuestionRequest(CBTAISchemaBase):
    """Regenerate one existing CBT question while preserving its question type."""

    subject: str = Field(min_length=1, max_length=200)
    academic_level: str = Field(min_length=1, max_length=200)
    topics: list[str] = Field(min_length=1, max_length=MAX_PUBLIC_TOPIC_COUNT)
    existing_question: AIExistingQuestion
    instruction: str = Field(min_length=1, max_length=MAX_PUBLIC_INSTRUCTION_LENGTH)
    visual_mode: AIVisualMode = "auto"
    context: str | None = Field(default=None, max_length=MAX_PUBLIC_TEXT_LENGTH)


class AIResolvedImageResponse(CBTAISchemaBase):
    source: Literal["search", "generated"]
    url: str | None = None
    data_base64: str | None = None
    content_type: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    alt_text: str | None = None
    source_url: str | None = None
    creator: str | None = None
    attribution_text: str | None = None
    license_name: str | None = None
    license_url: str | None = None


class AIQuestionOptionResponse(CBTAISchemaBase):
    text: str | None = None
    is_correct: bool
    image: AIResolvedImageResponse | None = None


class AIQuestionResponse(CBTAISchemaBase):
    question_type: AIQuestionType
    prompt: str
    instruction: str | None = None
    image: AIResolvedImageResponse | None = None
    options: list[AIQuestionOptionResponse]


class AICreditChargeResponse(CBTAISchemaBase):
    reservation_id: UUID
    credits_charged: int = Field(ge=0)
    credits_released: int = Field(ge=0)


class AIGenerateQuestionsResponse(CBTAISchemaBase):
    questions: list[AIQuestionResponse]
    repaired: bool
    charge: AICreditChargeResponse


class AIRegenerateQuestionResponse(CBTAISchemaBase):
    question: AIQuestionResponse
    repaired: bool
    charge: AICreditChargeResponse
