"""API contracts for performance-range comments and teacher term comments."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.report_cards.comment_models import (
    CommentTemplateOwnerType,
    CommentTemplateStatus,
    TeacherCommentStatus,
)


class InputBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class CommentTemplateCreate(InputBase):
    text: str = Field(min_length=1, max_length=2000)
    minimum_score: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    maximum_score: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    is_default: bool = False

    @model_validator(mode="after")
    def validate_range(self) -> "CommentTemplateCreate":
        if self.minimum_score > self.maximum_score:
            raise ValueError("minimum_score must be less than or equal to maximum_score")
        return self


class CommentTemplateUpdate(InputBase):
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    minimum_score: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
    )
    maximum_score: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        le=Decimal("100"),
    )
    is_default: bool | None = None
    status: CommentTemplateStatus | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> "CommentTemplateUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if self.status == CommentTemplateStatus.ARCHIVED and self.text is not None:
            raise ValueError("archive a comment separately from editing its text")
        if (
            self.minimum_score is not None
            and self.maximum_score is not None
            and self.minimum_score > self.maximum_score
        ):
            raise ValueError("minimum_score must be less than or equal to maximum_score")
        return self


class CommentTemplateResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    text: str
    minimum_score: Decimal
    maximum_score: Decimal
    is_default: bool
    owner_type: CommentTemplateOwnerType
    status: CommentTemplateStatus
    created_at: datetime
    updated_at: datetime


class CommentTemplateListResponse(OutputBase):
    items: list[CommentTemplateResponse]
    total: int


class TeacherCommentWrite(InputBase):
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    comment_text: str = Field(min_length=1, max_length=2000)
    source_template_id: uuid.UUID | None = None


class TeacherCommentResponse(OutputBase):
    id: uuid.UUID
    student_id: uuid.UUID
    student_enrollment_id: uuid.UUID
    class_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    teacher_membership_id: uuid.UUID
    # This historical storage field now contains the canonical weighted
    # report-scope performance percentage.
    average_snapshot: Decimal
    grade_snapshot: str
    comment_text: str
    source_template_id: uuid.UUID | None = None
    status: TeacherCommentStatus
    submitted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TeacherStudentCommentRow(OutputBase):
    student_id: uuid.UUID
    student_name: str | None = None
    admission_number: str
    academic_ready: bool
    readiness_label: str
    average: Decimal | None = None
    overall_grade: str | None = None
    comment_status: str
    comment: TeacherCommentResponse | None = None
    suggested_template: CommentTemplateResponse | None = None


class TeacherStudentCommentListResponse(OutputBase):
    class_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    items: list[TeacherStudentCommentRow]


class TeacherCommentClassScope(OutputBase):
    class_id: uuid.UUID
    academic_level_id: uuid.UUID
    class_name: str


class TeacherCommentDashboardSummary(OutputBase):
    classes: list[TeacherCommentClassScope] = Field(default_factory=list)
    class_teacher_class_count: int = 0
    students_requiring_comments: int = 0
    draft_comments: int = 0
    submitted_comments: int = 0
    needs_review_comments: int = 0
    comment_completion_percent: Decimal = Decimal("0")
    academic_session_id: uuid.UUID | None = None
    academic_term_id: uuid.UUID | None = None


class TeacherCommentOverrideRequest(InputBase):
    student_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    comment_text: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("reason cannot be empty")
        return value


class TeacherCommentOverrideResponse(OutputBase):
    id: uuid.UUID
    student_id: uuid.UUID
    student_enrollment_id: uuid.UUID
    class_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    admin_id: uuid.UUID
    comment_text: str
    reason: str
    created_at: datetime
