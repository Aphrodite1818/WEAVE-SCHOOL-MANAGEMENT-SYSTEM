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
    principal_comment: str | None = Field(default=None, min_length=1, max_length=2000)
    principal_template_id: uuid.UUID | None = None
    apply_default_principal_template: bool = False

    @model_validator(mode="after")
    def validate_target(self) -> "ReportCardGenerateRequest":
        if self.student_id is None and self.class_id is None:
            raise ValueError("Either student_id or class_id is required.")
        if self.student_id is not None and self.class_id is not None:
            raise ValueError("Provide either student_id or class_id, not both.")
        if self.principal_template_id is not None and self.apply_default_principal_template:
            raise ValueError("Choose an explicit principal template or grade defaults, not both.")
        if self.class_id is not None and (
            self.principal_template_id is not None or self.principal_comment is not None
        ):
            raise ValueError(
                "Class-wide generation cannot apply one principal comment to every student. "
                "Use personal grade defaults for bulk generation or generate one student at a time."
            )
        return self


class ReportCardPrincipalCommentUpdate(InputBase):
    principal_comment: str = Field(min_length=1, max_length=2000)
    principal_template_id: uuid.UUID | None = None


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
    academic_level_id: uuid.UUID | None = None
    academic_level_department_id: uuid.UUID | None = None
    class_name: str | None = None
    class_arm: str | None = None
    department_name: str | None = None
    class_teacher_name: str | None = None
    academic_session_id: uuid.UUID
    academic_session_name: str | None = None
    academic_term_id: uuid.UUID
    academic_term_name: str | None = None
    total_score: Decimal
    average_score: Decimal
    position: int | None = None
    position_out_of: int | None = None
    class_teacher_comment: str | None = None
    teacher_comment_source: str | None = None
    teacher_comment_source_id: uuid.UUID | None = None
    principal_comment: str | None = None
    principal_comment_source_template_id: uuid.UUID | None = None
    version: int = 1
    replaces_report_card_id: uuid.UUID | None = None
    published_at: datetime | None = None
    published_by: uuid.UUID | None = None
    is_outdated: bool = False
    superseded_at: datetime | None = None
    status: ReportCardStatus
    lines: list[ReportCardSubjectLineResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ReportCardListResponse(OutputBase):
    items: list[ReportCardResponse]
    total: int


class ReportCardClassOverviewRow(OutputBase):
    student_id: uuid.UUID
    student_name: str | None = None
    admission_number: str | None = None
    results_readiness: str
    submitted_count: int
    expected_count: int
    teacher_comment_status: str
    overall_grade: str | None = None
    principal_comment_status: str
    report_readiness: str
    report_card_id: uuid.UUID | None = None
    report_card_status: str | None = None
    report_card_version: int | None = None
    is_outdated: bool = False
    missing_subject_names: list[str] = Field(default_factory=list)


class ReportCardClassOverviewResponse(OutputBase):
    class_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    expected_subject_count: int
    items: list[ReportCardClassOverviewRow]


class ReportCardBulkGenerateResponse(OutputBase):
    generated: list[ReportCardResponse]
    skipped: list[dict]
