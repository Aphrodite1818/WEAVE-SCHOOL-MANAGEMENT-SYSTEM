"""Schemas for CBT -> Weave academic result ingestion."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CBTResultInputBase(BaseModel):
    """Base schema for payloads received from a paired CBT server."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class CBTResultOutputBase(BaseModel):
    """Base schema for payloads sent to a paired CBT server."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class CBTResultBulkScoreItem(CBTResultInputBase):
    """One student's score for the assessment component owned by the batch."""

    student_id: UUID

    score: Decimal = Field(
        ge=0,
        max_digits=5,
        decimal_places=2,
    )


class CBTResultBulkRequest(CBTResultInputBase):
    """Bulk component-score patch produced from one local CBT exam context."""

    # Worker/network idempotency identity.
    batch_id: UUID

    # Stable identity of the local CBT exam.
    # One source exam may be split across multiple network batches.
    source_exam_id: UUID

    # Shared academic context asserted by CBT.
    academic_session_id: UUID
    academic_term_id: UUID
    academic_level_id: UUID
    curriculum_subject_id: UUID
    assessment_component_id: UUID
    exam_date: date

    scores: list[CBTResultBulkScoreItem] = Field(
        min_length=1,
        max_length=1000,
    )

    @model_validator(mode="after")
    def validate_unique_students(self) -> CBTResultBulkRequest:
        student_ids = [item.student_id for item in self.scores]

        if len(student_ids) != len(set(student_ids)):
            raise ValueError("Each student may appear only once in a CBT result batch.")

        return self


class CBTResultBulkError(CBTResultOutputBase):
    """One student score rejected during bulk ingestion."""

    student_id: UUID
    code: str = Field(min_length=1, max_length=100)
    detail: str = Field(min_length=1, max_length=1000)


class CBTResultBulkResponse(CBTResultOutputBase):
    """Summary returned after processing one CBT result batch."""

    batch_id: UUID
    source_exam_id: UUID
    processed_at: datetime

    received: int = Field(ge=0)
    applied: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    rejected: int = Field(ge=0)

    errors: list[CBTResultBulkError] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_processing_counts(self) -> CBTResultBulkResponse:
        processed = self.applied + self.unchanged + self.rejected

        if processed != self.received:
            raise ValueError("Applied, unchanged and rejected counts must equal received count.")

        if len(self.errors) != self.rejected:
            raise ValueError("Each rejected score must have a corresponding error.")

        return self
