from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_PATCH_NULL_ERROR = "cannot be null; omit the field to leave the current value unchanged"


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CurriculumSubjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: uuid.UUID
    is_elective: bool = False
    academic_level_department_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("academic_level_department_ids")
    @classmethod
    def unique_departments(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise ValueError("department selections must be unique")
        return value


class CurriculumSubjectUpdate(BaseModel):
    """Update curriculum semantics; lifecycle uses dedicated endpoints."""

    model_config = ConfigDict(extra="forbid")

    is_elective: bool | None = None
    academic_level_department_ids: list[uuid.UUID] | None = None

    @field_validator("is_elective", mode="before")
    @classmethod
    def reject_null_boolean_updates(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} {_PATCH_NULL_ERROR}")
        return value

    @field_validator("academic_level_department_ids")
    @classmethod
    def unique_departments(cls, value: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("department selections must be unique")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "CurriculumSubjectUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one curriculum subject field must be provided")
        return self


class CurriculumSubjectDepartmentResponse(OutputBase):
    academic_level_department_id: uuid.UUID
    department_id: uuid.UUID
    department_name: str | None = None


class CurriculumSubjectResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    curriculum_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str | None = None
    subject_code: str | None = None
    is_elective: bool
    is_active: bool
    departments: list[CurriculumSubjectDepartmentResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CurriculumResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_level_id: uuid.UUID
    level_name: str | None = None
    subjects: list[CurriculumSubjectResponse] = Field(default_factory=list)


class ClassTermDepartmentSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_level_department_id: uuid.UUID


class ClassTermDepartmentResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    class_id: uuid.UUID
    academic_term_id: uuid.UUID
    academic_level_department_id: uuid.UUID
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    assigned_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ClassTermDepartmentCopyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_academic_term_id: uuid.UUID


class ClassTermDepartmentCopyResponse(OutputBase):
    copied: int
    skipped: int
    assignments: list[ClassTermDepartmentResponse] = Field(default_factory=list)


class AcademicLevelSpecializationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specialization_required_from_term_position: int = Field(ge=1, le=3)


class AcademicLevelSpecializationResponse(OutputBase):
    academic_level_id: uuid.UUID
    specialization_required_from_term_position: int
    is_configurable: bool


class ResolvedClassSubjectResponse(OutputBase):
    curriculum_subject_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str | None = None
    subject_code: str | None = None
    is_elective: bool
    is_general: bool
    matched_academic_level_department_id: uuid.UUID | None = None


class EligibleTeacherAssignmentClassResponse(OutputBase):
    class_id: uuid.UUID
    academic_level_id: uuid.UUID
    academic_level_name: str
    arm_label: str
    display_name: str
    department_name: str | None = None
    already_assigned: bool = False
