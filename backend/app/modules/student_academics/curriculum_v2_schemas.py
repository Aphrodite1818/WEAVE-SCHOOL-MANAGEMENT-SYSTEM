from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CurriculumSubjectCreate(BaseModel):
    subject_id: uuid.UUID
    is_elective: bool = False


class CurriculumSubjectUpdate(BaseModel):
    is_elective: bool | None = None
    is_active: bool | None = None


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
    academic_term_id: uuid.UUID
    department_id: uuid.UUID | None = None


class CurriculumOfferingResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    curriculum_subject_id: uuid.UUID
    academic_term_id: uuid.UUID
    department_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ClassTermDepartmentSet(BaseModel):
    department_id: uuid.UUID


class ClassTermDepartmentResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    class_id: uuid.UUID
    academic_term_id: uuid.UUID
    department_id: uuid.UUID
    assigned_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
