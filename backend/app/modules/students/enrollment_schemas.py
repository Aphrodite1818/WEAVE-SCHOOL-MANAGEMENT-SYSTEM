"""Request contracts for immutable student-enrollment placement changes."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnrollmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StudentClassChangeRequest(EnrollmentInput):
    """Reclassify a student between classes in the same level/session."""

    target_class_id: uuid.UUID
    academic_session_id: uuid.UUID
    effective_date: date = Field(default_factory=date.today)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("effective_date cannot be in the future")
        return value

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("reason cannot be empty")
        return cleaned


class StudentBatchClassAssignmentRequest(EnrollmentInput):
    """Place currently-unassigned students into one class."""

    student_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    target_class_id: uuid.UUID
    effective_date: date = Field(default_factory=date.today)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("student_ids")
    @classmethod
    def unique_students(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise ValueError("student_ids must not contain duplicates")
        return value

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("effective_date cannot be in the future")
        return value

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("reason cannot be empty")
        return cleaned
