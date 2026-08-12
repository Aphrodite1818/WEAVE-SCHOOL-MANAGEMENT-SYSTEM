"""Academic session, assignment, result, card, and progression schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.utils.normalization import normalize_class_name, normalize_grade
from app.core.utils.validators import validate_academic_session_name
from app.modules.student_academics.models import (
    AcademicResultStatus,
    AcademicSessionStatus,
    AcademicTermName,
    AcademicTermStatus,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
    StudentProgressionRunStatus,
)


class InputBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class OutputBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
    )

    @field_validator("class_name", mode="before", check_fields=False)
    @classmethod
    def normalize_response_class_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_class_name(value) or value


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
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date <= self.start_date
        ):
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
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date <= self.start_date
        ):
            raise ValueError("end_date must be after start_date")
        return self


class AcademicSessionOpenRequest(InputBase):
    confirmation: Literal["OPEN_ACADEMIC_SESSION"]


class AcademicSessionDeleteRequest(InputBase):
    confirmation: Literal["DELETE_ACADEMIC_SESSION"]


class AcademicSessionResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    start_date: date | None = None
    end_date: date | None = None
    status: AcademicSessionStatus
    is_current: bool
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

    @model_validator(mode="after")
    def validate_dates(self) -> AcademicTermCreate:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date <= self.start_date
        ):
            raise ValueError("end_date must be after start_date")

        return self


class AcademicTermUpdate(InputBase):
    name: AcademicTermName | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_update(self) -> AcademicTermUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one term field must be provided")

        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date <= self.start_date
        ):
            raise ValueError("end_date must be after start_date")

        return self


class AcademicTermOpenRequest(InputBase):
    confirmation: Literal["OPEN_ACADEMIC_TERM"]


class AcademicTermCloseRequest(InputBase):
    confirmation: Literal["CLOSE_ACADEMIC_TERM"]


class AcademicTermStartClosingRequest(InputBase):
    confirmation: Literal["START_TERM_CLOSING"]


class AcademicTermFinalizeCloseRequest(InputBase):
    confirmation: Literal["FINALIZE_TERM_CLOSE"]


class AcademicTermCancelClosureRequest(InputBase):
    confirmation: Literal["CANCEL_TERM_CLOSURE"]
    reason: str = Field(min_length=3, max_length=500)


class AcademicTermDeleteRequest(InputBase):
    confirmation: Literal["DELETE_ACADEMIC_TERM"]


class AcademicTermResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_session_id: uuid.UUID
    name: AcademicTermName
    start_date: date | None = None
    end_date: date | None = None

    status: AcademicTermStatus
    is_current: bool

    opened_at: datetime | None = None
    closing_started_at: datetime | None = None
    closed_at: datetime | None = None
    opened_by_admin_id: uuid.UUID | None = None
    closed_by_admin_id: uuid.UUID | None = None

    created_at: datetime
    updated_at: datetime


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

    @field_validator("grade", mode="before")
    @classmethod
    def normalize_grade_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_grade(value)


class AcademicTermResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_session_id: uuid.UUID
    name: AcademicTermName
    start_date: date | None = None
    end_date: date | None = None

    status: AcademicTermStatus
    is_current: bool

    opened_at: datetime | None = None
    closing_started_at: datetime | None = None
    closed_at: datetime | None = None
    opened_by_admin_id: uuid.UUID | None = None
    closed_by_admin_id: uuid.UUID | None = None

    created_at: datetime
    updated_at: datetime


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

    @field_validator("grade", mode="before")
    @classmethod
    def normalize_grade_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_grade(value)
        if normalized is None:
            raise ValueError("grade cannot be empty")
        return normalized


class GradingScaleResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    min_score: Decimal
    max_score: Decimal
    grade: str
    remark: str | None = None
    is_active: bool


class GradingScaleDependencyPreview(OutputBase):
    scale_id: uuid.UUID
    dependency_counts: dict[str, int]
    can_deactivate: bool
    can_delete: bool
    blocker_messages: list[str] = []


class GradingScaleReadiness(OutputBase):
    is_ready: bool
    missing_coverage: list[str] = []
    overlaps: list[str] = []
    messages: list[str] = []


class LevelSubjectCreate(InputBase):
    subject_id: uuid.UUID
    is_core: bool = False


class LevelSubjectBulkCreate(InputBase):
    subject_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    is_core: bool = False

    @field_validator("subject_ids")
    @classmethod
    def subject_ids_must_be_unique(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("subject_ids must not contain duplicates")
        return value


class LevelSubjectUpdate(InputBase):
    is_core: bool


class LevelSubjectResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_level_id: uuid.UUID
    academic_level_name: str | None = None
    subject_id: uuid.UUID
    subject_name: str | None = None
    subject_code: str | None = None
    is_core: bool
    is_active: bool
    lifecycle_status: Literal["active", "inactive", "archived"]
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    level_is_active: bool | None = None
    level_is_archived: bool | None = None
    subject_is_active: bool | None = None
    subject_is_archived: bool | None = None
    can_activate: bool
    activation_blocker: str | None = None
    created_at: datetime
    updated_at: datetime


class LevelSubjectActivateRequest(InputBase):
    confirmation: Literal["ACTIVATE_LEVEL_SUBJECT"]


class LevelSubjectDeactivateRequest(InputBase):
    confirmation: Literal["DEACTIVATE_LEVEL_SUBJECT"]


class LevelSubjectArchiveRequest(InputBase):
    confirmation: Literal["ARCHIVE_LEVEL_SUBJECT"]


class LevelSubjectRestoreRequest(InputBase):
    confirmation: Literal["RESTORE_LEVEL_SUBJECT"]


class LevelSubjectDeleteRequest(InputBase):
    confirmation: Literal["DELETE_LEVEL_SUBJECT"]


class TeacherAssignmentCreate(InputBase):
    teacher_membership_id: uuid.UUID
    class_id: uuid.UUID
    level_subject_id: uuid.UUID
    effective_from: date | None = None


class TeacherAssignmentReassign(InputBase):
    teacher_membership_id: uuid.UUID
    effective_from: date | None = None


class TeacherAssignmentEnd(InputBase):
    effective_to: date | None = None


class TeacherAssignmentDelete(InputBase):
    confirmation: Literal["DELETE_TEACHER_ASSIGNMENT"]


class TeacherAssignmentDependencyPreview(OutputBase):
    assignment_id: uuid.UUID
    dependency_counts: dict[str, int]
    can_end: bool
    can_reassign: bool
    can_delete: bool
    blocker_messages: list[str] = []


class AcademicSessionDependencyPreview(OutputBase):
    session_id: uuid.UUID
    dependency_counts: dict[str, int]
    blocker_messages: list[str] = []
    can_open: bool
    can_close: bool
    can_start_closing: bool
    can_progress: bool
    can_delete: bool


class AcademicTermDependencyPreview(OutputBase):
    term_id: uuid.UUID
    dependency_counts: dict[str, int]
    blocker_messages: list[str] = []
    can_open: bool
    can_close: bool
    can_start_closing: bool = False
    can_finalize_close: bool = False
    can_cancel_closure: bool = False
    can_delete: bool


class TeacherAssignmentResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    level_subject_id: uuid.UUID
    teacher_membership_id: uuid.UUID
    class_id: uuid.UUID
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


class StudentSubjectResultUpsert(InputBase):
    student_id: uuid.UUID
    teacher_assignment_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    component_scores: list["StudentAssessmentScoreUpsert"] = Field(default_factory=list)
    status: AcademicResultStatus = AcademicResultStatus.DRAFT

    @model_validator(mode="after")
    def validate_result(self):
        component_ids = [item.assessment_component_id for item in self.component_scores]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("assessment components must be unique")
        return self


class StudentAssessmentScoreUpsert(InputBase):
    assessment_component_id: uuid.UUID
    score: Decimal | None = Field(default=None, ge=0)


class AssessmentComponentScoreResponse(OutputBase):
    assessment_component_id: uuid.UUID
    name: str
    code: str | None = None
    position: int
    maximum_score: Decimal
    score: Decimal | None = None


class StudentSubjectResultStatusUpdate(InputBase):
    status: AcademicResultStatus


class StudentSubjectResultFilter(InputBase):
    subject_id: uuid.UUID | None = None
    status: AcademicResultStatus | None = None
    search: str | None = None
    is_complete: bool | None = None
    has_grade: bool | None = None
    teacher_assignment_id: uuid.UUID | None = None


class StudentSubjectResultReopenRequest(InputBase):
    reason: str = Field(min_length=3, max_length=1000)


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
    level_subject_id: uuid.UUID
    teacher_assignment_id: uuid.UUID | None = None
    academic_session_id: uuid.UUID
    academic_session_name: str | None = None
    academic_term_id: uuid.UUID
    academic_term_name: str | None = None
    assessment_scheme_id: uuid.UUID
    assessment_scheme_name: str
    components: list[AssessmentComponentScoreResponse] = Field(default_factory=list)
    maximum_score: Decimal = Decimal("100")
    total_score: Decimal
    grade: str | None = None
    remark: str | None = None
    status: AcademicResultStatus
    recorded_by_actor_type: str
    recorded_by_actor_id: uuid.UUID
    submitted_at: datetime | None = None
    submitted_by_actor_type: str | None = None
    submitted_by_actor_id: uuid.UUID | None = None
    approved_at: datetime | None = None
    approved_by_admin_id: uuid.UUID | None = None
    locked_at: datetime | None = None
    locked_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class StudentSubjectCardResponse(OutputBase):
    id: uuid.UUID
    result_id: uuid.UUID | None = None
    class_id: uuid.UUID
    class_name: str | None = None
    class_arm: str | None = None
    subject_id: uuid.UUID
    subject_name: str | None = None
    subject_code: str | None = None
    teacher_membership_id: uuid.UUID | None = None
    teacher_name: str | None = None
    academic_session_id: uuid.UUID | None = None
    academic_session_name: str | None = None
    academic_term_id: uuid.UUID | None = None
    academic_term_name: str | None = None
    assessment_scheme_id: uuid.UUID | None = None
    assessment_scheme_name: str | None = None
    components: list[AssessmentComponentScoreResponse] = Field(default_factory=list)
    maximum_score: Decimal = Decimal("100")
    total_score: Decimal | None = None
    grade: str | None = None
    remark: str | None = None
    status: str = "pending"
    is_complete: bool = False


class StudentSubjectCardContextResponse(OutputBase):
    class_id: uuid.UUID | None = None
    class_name: str | None = None
    class_arm: str | None = None
    academic_session_id: uuid.UUID | None = None
    academic_session_name: str | None = None
    academic_term_id: uuid.UUID | None = None
    academic_term_name: str | None = None


class StudentSubjectCardListResponse(OutputBase):
    items: list[StudentSubjectCardResponse]
    total: int
    context: StudentSubjectCardContextResponse


class StudentProgressionItemResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    progression_run_id: uuid.UUID
    student_id: uuid.UUID
    from_enrollment_id: uuid.UUID | None = None
    to_enrollment_id: uuid.UUID | None = None
    from_class_id: uuid.UUID
    to_class_id: uuid.UUID | None = None
    selected_level_id: uuid.UUID | None = None
    selected_classroom_id: uuid.UUID | None = None
    action: StudentProgressionItemAction
    status: StudentProgressionItemStatus
    reason: str | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProgressionDestinationResponse(OutputBase):
    id: uuid.UUID
    target_type: str
    label: str
    academic_level_id: uuid.UUID


class StudentProgressionSelectionResponse(OutputBase):
    item: StudentProgressionItemResponse
    student_name: str | None = None
    admission_number: str | None = None
    source_class_label: str | None = None
    selection_target_type: str | None = None
    selected_destination_label: str | None = None
    destinations: list[ProgressionDestinationResponse] = Field(default_factory=list)


class StudentProgressionSelectionRequest(InputBase):
    destination_id: uuid.UUID


class AdminProgressionPlacementRequest(InputBase):
    classroom_id: uuid.UUID


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
    pending_students: int = Field(ge=0)
    failed_students: int = Field(ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    initiated_by_admin_id: uuid.UUID | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class StudentProgressionRunDetailResponse(StudentProgressionRunResponse):
    items: list[StudentProgressionItemResponse]


class AcademicSessionListResponse(OutputBase):
    items: list[AcademicSessionResponse]
    total: int


class AcademicTermListResponse(OutputBase):
    items: list[AcademicTermResponse]
    total: int


class GradingScaleListResponse(OutputBase):
    items: list[GradingScaleResponse]
    total: int


class LevelSubjectListResponse(OutputBase):
    items: list[LevelSubjectResponse]
    total: int


class TeacherAssignmentListResponse(OutputBase):
    items: list[TeacherAssignmentResponse]
    total: int


class StudentSubjectResultListResponse(OutputBase):
    items: list[StudentSubjectResultResponse]
    total: int


class StudentProgressionRunListResponse(OutputBase):
    items: list[StudentProgressionRunResponse]
    total: int = Field(ge=0)
