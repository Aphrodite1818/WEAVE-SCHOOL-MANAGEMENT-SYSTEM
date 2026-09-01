from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


_PATCH_NULL_ERROR = "cannot be null; omit the field to leave the current value unchanged"


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CurriculumSubjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_id: uuid.UUID
    is_elective: bool = False


class CurriculumSubjectUpdate(BaseModel):
    """Semantic configuration only; lifecycle uses dedicated endpoints."""

    model_config = ConfigDict(extra="forbid")
    is_elective: bool | None = None

    @field_validator("is_elective", mode="before")
    @classmethod
    def reject_null_boolean_updates(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} {_PATCH_NULL_ERROR}")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "CurriculumSubjectUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one curriculum subject field must be provided")
        return self


class CurriculumSubjectResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    curriculum_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str | None = None
    subject_code: str | None = None
    is_elective: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CurriculumResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_level_id: uuid.UUID
    level_name: str | None = None
    subjects: list[CurriculumSubjectResponse] = []


class CurriculumOfferingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    academic_term_id: uuid.UUID
    academic_level_department_id: uuid.UUID | None = None


class CurriculumOfferingResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    curriculum_subject_id: uuid.UUID
    academic_term_id: uuid.UUID
    academic_level_department_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    created_at: datetime
    updated_at: datetime


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
