# ====================================== #
#              schemas.py                #
# ====================================== #

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.utils.normalization import normalize_class_arm, normalize_class_name


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
    next_level_id: uuid.UUID | None
    is_terminal: bool
    is_active: bool
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class AcademicLevelProgressionConfigureRequest(InputBase):
    next_level_id: uuid.UUID | None = None
    is_terminal: bool = False

    @model_validator(mode="after")
    def validate_terminal_configuration(self):
        if self.is_terminal and self.next_level_id is not None:
            raise ValueError("a terminal academic level cannot have next_level_id")
        if not self.is_terminal and self.next_level_id is None:
            raise ValueError(
                "choose a next academic level or mark this level as terminal"
            )
        return self


class AcademicLevelProgressionResponse(OutputBase):
    academic_level_id: uuid.UUID
    academic_level_name: str
    next_level_id: uuid.UUID | None = None
    next_level_name: str | None = None
    is_terminal: bool
    is_active: bool


class ClassRoomBase(InputBase):
    academic_level_id: uuid.UUID
    arm: str = Field(min_length=1, max_length=20)
    teacher_membership_id: uuid.UUID | None = None

    @field_validator("arm", mode="before")
    @classmethod
    def normalize_arm(cls, value: str | None) -> str | None:
        return normalize_class_arm(value)


class ClassRoomCreate(ClassRoomBase):
    pass


class ClassRoomUpdate(InputBase):
    academic_level_id: uuid.UUID | None = None
    arm: str | None = Field(default=None, min_length=1, max_length=20)
    teacher_membership_id: uuid.UUID | None = None

    @field_validator("arm", mode="before")
    @classmethod
    def normalize_arm(cls, value: str | None) -> str | None:
        return normalize_class_arm(value)


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
    arm: str

    teacher_membership_id: uuid.UUID | None
    is_active: bool
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
