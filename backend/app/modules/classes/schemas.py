# ====================================== #
#              schemas.py                #
# ====================================== #

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.utils.normalization import normalize_class_name
from app.modules.classes.models import AcademicCategory


class InputBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        str_to_lower=False,
        use_enum_values=False,
    )


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True, populate_by_name=True)


class AcademicLevelBase(InputBase):
    name: str = Field(min_length=1, max_length=100)
    category: AcademicCategory
    position: int = Field(gt=0)
    specialization_required_from_term_position: int | None = Field(default=None, gt=0)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_class_name(value)
        if normalized is None:
            raise ValueError("academic level name cannot be empty")
        return normalized


class AcademicLevelCreate(AcademicLevelBase):
    pass


class AcademicLevelUpdate(InputBase):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: AcademicCategory | None = None
    position: int | None = Field(default=None, gt=0)
    specialization_required_from_term_position: int | None = Field(default=None, gt=0)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_class_name(value)
        if normalized is None:
            raise ValueError("academic level name cannot be empty")
        return normalized


class AcademicLevelResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    category: AcademicCategory
    position: int
    specialization_required_from_term_position: int | None = None
    is_active: bool
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class DepartmentCreate(InputBase):
    name: str = Field(min_length=1, max_length=100)


class DepartmentResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    is_active: bool
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ArmLabelCreate(InputBase):
    label: str = Field(min_length=1, max_length=20)
    position: int | None = Field(default=None, gt=0)


class ArmLabelUpdate(InputBase):
    label: str | None = Field(default=None, min_length=1, max_length=20)
    position: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ArmLabelResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    label: str
    position: int | None = None
    is_active: bool
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ClassRoomBase(InputBase):
    academic_level_id: uuid.UUID
    department_id: uuid.UUID | None = None
    arm_label_id: uuid.UUID | None = None
    teacher_membership_id: uuid.UUID | None = None


class ClassRoomCreate(ClassRoomBase):
    pass


class ClassRoomUpdate(InputBase):
    academic_level_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    arm_label_id: uuid.UUID | None = None
    teacher_membership_id: uuid.UUID | None = None


class ClassRoomArchiveRequest(InputBase):
    confirmation: Literal["ARCHIVE_CLASSROOM"]


class ClassRoomActivateRequest(InputBase):
    confirmation: Literal["ACTIVATE_CLASSROOM"]


class ClassRoomDeactivateRequest(InputBase):
    confirmation: Literal["DEACTIVATE_CLASSROOM"]


class ClassRoomRestoreRequest(InputBase):
    confirmation: Literal["RESTORE_CLASSROOM"]


class ClassRoomResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID

    academic_level_id: uuid.UUID
    academic_level_name: str
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    arm_label_id: uuid.UUID | None = None
    arm_label: str | None = None
    display_name: str

    teacher_membership_id: uuid.UUID | None
    is_active: bool
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
