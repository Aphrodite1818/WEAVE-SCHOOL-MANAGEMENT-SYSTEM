"""Academic session, assignment, result, and progression schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.utils.normalization import normalize_grade
from app.core.utils.validators import validate_academic_session_name
from app.modules.student_academics.models import (
    AcademicResultStatus,
    AcademicSessionStatus,
    AcademicTermName,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
    StudentProgressionRunStatus,
)


class InputBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=False)


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True, populate_by_name=True)


class AcademicSessionCreate(InputBase):
    name: str = Field(min_length=9, max_length=9)
    start_date: date | None = None
    end_date: date | None = None
    next_academic_session_id: uuid.UUID | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_academic_session_name(value)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date is not None and self.end_date is not None and self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class AcademicSessionUpdate(InputBase):
    name: str | None = Field(default=None, min_length=9, max_length=9)
    start_date: date | None = None
    end_date: date | None = None
    next_academic_session_id: uuid.UUID | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return None if value is None else validate_academic_session_name(value)

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("at least one session field must be provided")
        if self.start_date is not None and self.end_date is not None and self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class AcademicSessionOpenRequest(InputBase):
    confirmation: Literal["OPEN_ACADEMIC_SESSION"]


class AcademicSessionCloseRequest(InputBase):
    idempotency_key: str = Field(min_length=8, max_length=150)
    confirmation: Literal["CLOSE_AND_PROGRESS"]


class AcademicSessionResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    start_date: date | None = None
    end_date: date | None = None
    status: AcademicSessionStatus
    is_current: bool
    is_active: bool
    closing_started_at: datetime | None = None
    closed_at: datetime | None = None
    closed_by_admin_id: uuid.UUID | None = None
    next_academic_session_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class AcademicTermCreate(InputBase):
    academic_session_id: uuid.UUID
    name: AcademicTermName
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    is_active: bool = True


class AcademicTermUpdate(InputBase):
    name: AcademicTermName | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    is_active: bool | None = None


class AcademicTermResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_session_id: uuid.UUID
    name: AcademicTermName
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool
    is_active: bool


class GradingScaleCreate(InputBase):
    min_score: Decimal = Field(ge=0, le=100)
    max_score: Decimal = Field(ge=0, le=100)
    grade: str = Field(min_length=1, max_length=10)
    remark: str | None = Field(default=None, max_length=100)
    is_active: bool = True

    @field_validator("grade", mode="before")
    @classmethod
    def normalize_grade_value(cls, value: str) -> str:
        normalized = normalize_grade(value)
        if normalized is None:
            raise ValueError("grade cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_range(self):
        if self.min_score > self.max_score:
            raise ValueError("minimum score cannot exceed maximum score")
        return self


class GradingScaleUpdate(InputBase):
    min_score: Decimal | None = Field(default=None, ge=0, le=100)
    max_score: Decimal | None = Field(default=None, ge=0, le=100)
    grade: str | None = Field(default=None, min_length=1, max_length=10)
    remark: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class GradingScaleResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    min_score: Decimal
    max_score: Decimal
    grade: str
    remark: str | None = None
    is_active: bool


class ClassSubjectCreate(InputBase):
    subject_id: uuid.UUID
    is_core: bool = False


class ClassSubjectResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str | None = None
    subject_code: str | None = None
    is_core: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TeacherAssignmentCreate(InputBase):
    teacher_membership_id: uuid.UUID
    class_subject_id: uuid.UUID


class TeacherAssignmentReassign(InputBase):
    teacher_membership_id: uuid.UUID


class TeacherAssignmentResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    class_subject_id: uuid.UUID
    teacher_membership_id: uuid.UUID
    class_id: uuid.UUID | None = None
    class_name: str | None = None
    class_arm: str | None = None
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    subject_code: str | None = None
    teacher_name: str | None = None
    teacher_staff_id: str | None = None
    is_active: bool
    effective_from: date
    effective_to: date | None = None
    created_at: datetime
    updated_at: datetime


class ClassSubjectTeacherCreate(InputBase):
    class_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_membership_id: uuid.UUID
    is_core: bool = True
    sort_order: int = 0
    is_active: bool = True


class ClassSubjectTeacherUpdate(InputBase):
    teacher_membership_id: uuid.UUID | None = None
    is_core: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class ClassSubjectTeacherResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_membership_id: uuid.UUID
    is_core: bool
    sort_order: int
    is_active: bool


class StudentSubjectResultUpsert(InputBase):
    student_id: uuid.UUID
    teacher_assignment_id: uuid.UUID | None = None
    class_subject_teacher_id: uuid.UUID | None = None
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    test_score: Decimal | None = Field(default=None, ge=0, le=100)
    assessment_score: Decimal | None = Field(default=None, ge=0, le=100)
    exam_score: Decimal | None = Field(default=None, ge=0, le=100)
    status: AcademicResultStatus = AcademicResultStatus.DRAFT

    @model_validator(mode="after")
    def validate_result(self):
        if self.teacher_assignment_id is None and self.class_subject_teacher_id is None:
            raise ValueError("an assignment reference is required")
        total = sum((score for score in (self.test_score, self.assessment_score, self.exam_score) if score is not None), Decimal("0"))
        if total > 100:
            raise ValueError("combined score cannot exceed 100")
        if self.status == AcademicResultStatus.SUBMITTED and any(
            score is None for score in (self.test_score, self.assessment_score, self.exam_score)
        ):
            raise ValueError("all scores are required before submission")
        return self


class StudentSubjectResultStatusUpdate(InputBase):
    status: AcademicResultStatus


class StudentSubjectResultResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str | None = None
    admission_number: str | None = None
    class_id: uuid.UUID
    class_name: str | None = None
    class_arm: str | None = None
    subject_id: uuid.UUID
    subject_name: str | None = None
    subject_code: str | None = None
    teacher_membership_id: uuid.UUID
    teacher_name: str | None = None
    class_subject_teacher_id: uuid.UUID
    teacher_assignment_id: uuid.UUID | None = None
    academic_session_id: uuid.UUID
    academic_session_name: str | None = None
    academic_term_id: uuid.UUID
    academic_term_name: str | None = None
    test_score: Decimal | None = None
    assessment_score: Decimal | None = None
    exam_score: Decimal | None = None
    total_score: Decimal
    grade: str | None = None
    remark: str | None = None
    status: AcademicResultStatus
    recorded_by_actor_type: str
    recorded_by_actor_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class StudentProgressionItemResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    progression_run_id: uuid.UUID
    student_id: uuid.UUID
    from_enrollment_id: uuid.UUID | None = None
    to_enrollment_id: uuid.UUID | None = None
    from_class_id: uuid.UUID
    to_class_id: uuid.UUID | None = None
    action: StudentProgressionItemAction
    status: StudentProgressionItemStatus
    reason: str | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StudentProgressionRunResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_session_id: uuid.UUID
    next_academic_session_id: uuid.UUID
    idempotency_key: str
    status: StudentProgressionRunStatus
    total_students: int = Field(ge=0)
    promoted_students: int = Field(ge=0)
    graduated_students: int = Field(ge=0)
    skipped_students: int = Field(ge=0)
    failed_students: int = Field(ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    initiated_by_admin_id: uuid.UUID | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class StudentProgressionRunDetailResponse(StudentProgressionRunResponse):
    items: list[StudentProgressionItemResponse]


class AcademicSessionCloseResponse(OutputBase):
    closed_session: AcademicSessionResponse
    opened_session: AcademicSessionResponse
    progression_run: StudentProgressionRunDetailResponse


class AcademicSessionListResponse(OutputBase):
    items: list[AcademicSessionResponse]
    total: int


class AcademicTermListResponse(OutputBase):
    items: list[AcademicTermResponse]
    total: int


class GradingScaleListResponse(OutputBase):
    items: list[GradingScaleResponse]
    total: int


class ClassSubjectListResponse(OutputBase):
    items: list[ClassSubjectResponse]
    total: int


class TeacherAssignmentListResponse(OutputBase):
    items: list[TeacherAssignmentResponse]
    total: int


class ClassSubjectTeacherListResponse(OutputBase):
    items: list[ClassSubjectTeacherResponse]
    total: int


class StudentSubjectResultListResponse(OutputBase):
    items: list[StudentSubjectResultResponse]
    total: int


class StudentProgressionRunListResponse(OutputBase):
    items: list[StudentProgressionRunResponse]
    total: int = Field(ge=0)
