"""Academic structure request and response contracts."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.utils.normalization import normalize_class_name
from app.modules.classes.models import AcademicCategory, AcademicLevelStatus


_PATCH_NULL_ERROR = "cannot be null; omit the field to leave the current value unchanged"


class InputBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=False)


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True, populate_by_name=True)


class AcademicCategoryOption(OutputBase):
    value: AcademicCategory
    label: str
    position: int
    supports_departments: bool


class AcademicLevelBase(InputBase):
    name: str = Field(min_length=1, max_length=100)
    category: AcademicCategory
    position: int = Field(gt=0)
    specialization_required_from_term_position: int | None = Field(default=None, ge=1, le=3)

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

    # none deliberately means this level
    # does not require department specialization

    specialization_required_from_term_position: int | None = Field(default=None, ge=1, le=3)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name_patch(cls, value: str | None) -> str:
        if value is None:
            raise ValueError(f"name {_PATCH_NULL_ERROR}")
        normalized = normalize_class_name(value)
        if normalized is None:
            raise ValueError("academic level name cannot be empty")
        return normalized

    @field_validator("category", "position", mode="before")
    @classmethod
    def reject_null_required_fields(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} {_PATCH_NULL_ERROR}")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "AcademicLevelUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one academic level field must be provided")
        return self


class AcademicLevelResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    category: AcademicCategory
    position: int
    status: AcademicLevelStatus
    specialization_required_from_term_position: int | None = None
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class DepartmentCreate(InputBase):
    name: str = Field(min_length=1, max_length=100)


class DepartmentUpdate(InputBase):
    name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def reject_null_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError(f"name {_PATCH_NULL_ERROR}")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "DepartmentUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one department field must be provided")
        return self


class DepartmentResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_level_id: uuid.UUID
    name: str
    is_active: bool
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ArmLabelCreate(InputBase):
    label: str = Field(min_length=1, max_length=20)


class ArmLabelUpdate(InputBase):
    label: str | None = Field(default=None, min_length=1, max_length=20)
    is_active: bool | None = None

    @field_validator("label", "is_active", mode="before")
    @classmethod
    def reject_null_required_fields(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} {_PATCH_NULL_ERROR}")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "ArmLabelUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one arm label field must be provided")
        return self


class ArmLabelResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    label: str
    is_active: bool
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ClassRoomCreate(InputBase):
    academic_level_id: uuid.UUID
    arm_label_id: uuid.UUID
    teacher_membership_id: uuid.UUID | None = None


class ClassRoomUpdate(InputBase):
    academic_level_id: uuid.UUID | None = None
    arm_label_id: uuid.UUID | None = None
    teacher_membership_id: uuid.UUID | None = None

    @field_validator("academic_level_id", "arm_label_id", mode="before")
    @classmethod
    def reject_null_required_fields(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} {_PATCH_NULL_ERROR}")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "ClassRoomUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one class field must be provided")
        return self


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
    arm_label_id: uuid.UUID
    arm_label: str
    display_name: str
    teacher_membership_id: uuid.UUID | None
    is_active: bool
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
