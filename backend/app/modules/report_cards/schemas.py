import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.utils.normalization import normalize_class_name
from app.modules.report_cards.models import ReportCardStatus


class InputBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=True,
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


class ReportCardGenerateRequest(InputBase):
    student_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    generate_for_class: bool | None = None

    @model_validator(mode="after")
    def validate_target(self):
        if self.student_id is None and self.class_id is None:
            raise ValueError("Either student_id or class_id is required.")
        if self.student_id is not None and self.class_id is not None:
            raise ValueError("Provide either student_id or class_id, not both.")
        return self


class ReportCardCommentsUpdate(InputBase):
    """Sparse report-card comment update; explicit null clears a comment."""

    class_teacher_comment: str | None = Field(default=None, max_length=2000)
    principal_comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_patch_field(self) -> "ReportCardCommentsUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one report card comment field must be provided")
        return self


class ReportCardSubjectComponentResponse(OutputBase):
    assessment_component_id: uuid.UUID
    name: str
    code: str | None = None
    position: int
    maximum_score: Decimal
    score: Decimal


class ReportCardSubjectLineResponse(OutputBase):
    id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
    subject_code: str | None = None
    teacher_name: str | None = None
    components: list[ReportCardSubjectComponentResponse] = Field(default_factory=list)
    total_score: Decimal
    grade: str
    remark: str | None = None


class ReportCardResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    school_name: str | None = None
    school_logo_url: str | None = None
    school_address: str | None = None
    school_phone: str | None = None
    school_email: str | None = None
    student_id: uuid.UUID
    student_name: str | None = None
    admission_number: str | None = None
    student_passport_photo_url: str | None = None
    class_id: uuid.UUID | None = None
    class_name: str | None = None
    class_arm: str | None = None
    academic_session_id: uuid.UUID
    academic_session_name: str | None = None
    academic_term_id: uuid.UUID
    academic_term_name: str | None = None
    total_score: Decimal
    average_score: Decimal
    position: int | None = None
    position_out_of: int | None = None
    class_teacher_comment: str | None = None
    principal_comment: str | None = None
    version: int = 1
    published_at: datetime | None = None
    published_by: uuid.UUID | None = None
    is_outdated: bool = False
    superseded_at: datetime | None = None
    status: ReportCardStatus
    lines: list[ReportCardSubjectLineResponse] = []
    created_at: datetime
    updated_at: datetime


class ReportCardListResponse(OutputBase):
    items: list[ReportCardResponse]
    total: int


class ReportCardClassOverviewRow(OutputBase):
    student_id: uuid.UUID
    student_name: str | None = None
    admission_number: str | None = None
    submitted_count: int
    expected_count: int
    report_card_id: uuid.UUID | None = None
    report_card_status: str | None = None
    report_card_version: int | None = None
    is_outdated: bool = False
    missing_subject_names: list[str] = []


class ReportCardClassOverviewResponse(OutputBase):
    class_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    expected_subject_count: int
    items: list[ReportCardClassOverviewRow]


class ReportCardBulkGenerateResponse(OutputBase):
    generated: list[ReportCardResponse]
    skipped: list[dict]
