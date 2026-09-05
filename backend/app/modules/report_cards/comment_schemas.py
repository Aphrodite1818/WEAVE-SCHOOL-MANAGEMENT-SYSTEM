"""API contracts for personal comment templates and teacher term comments."""

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


class CommentTemplateWrite(InputBase):
    name: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=2000)
    grading_scale_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    default_grading_scale_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_defaults(self) -> "CommentTemplateWrite":
        grade_ids = set(self.grading_scale_ids)
        defaults = set(self.default_grading_scale_ids)
        if len(grade_ids) != len(self.grading_scale_ids):
            raise ValueError("grading_scale_ids must not contain duplicates")
        if len(defaults) != len(self.default_grading_scale_ids):
            raise ValueError("default_grading_scale_ids must not contain duplicates")
        if not defaults.issubset(grade_ids):
            raise ValueError("defaults must also appear in grading_scale_ids")
        return self


class CommentTemplateUpdate(InputBase):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    status: CommentTemplateStatus | None = None
    grading_scale_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)
    default_grading_scale_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_patch(self) -> "CommentTemplateUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if self.status == CommentTemplateStatus.ARCHIVED and (
            self.name is not None or self.text is not None
        ):
            raise ValueError("archive a template separately from editing its content")
        grade_ids = set(self.grading_scale_ids or [])
        defaults = set(self.default_grading_scale_ids or [])
        if self.grading_scale_ids is not None and len(grade_ids) != len(self.grading_scale_ids):
            raise ValueError("grading_scale_ids must not contain duplicates")
        if self.default_grading_scale_ids is not None and len(defaults) != len(
            self.default_grading_scale_ids
        ):
            raise ValueError("default_grading_scale_ids must not contain duplicates")
        if self.default_grading_scale_ids is not None:
            if self.grading_scale_ids is None:
                raise ValueError("grading_scale_ids is required when defaults are changed")
            if not defaults.issubset(grade_ids):
                raise ValueError("defaults must also appear in grading_scale_ids")
        return self


class CommentTemplateResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    text: str
    owner_type: CommentTemplateOwnerType
    status: CommentTemplateStatus
    grading_scale_ids: list[uuid.UUID] = Field(default_factory=list)
    default_grading_scale_ids: list[uuid.UUID] = Field(default_factory=list)
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
