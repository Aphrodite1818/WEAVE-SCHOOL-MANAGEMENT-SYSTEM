# ====================================== #
#              schemas.py                #
# ====================================== #

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.utils.normalization import normalize_class_arm, normalize_class_name
from app.modules.classes.models import (
    AcademicLevelProgressionMode,
    ProgressionSelectionTargetType,
)


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
    progression_mode: AcademicLevelProgressionMode
    selection_target_type: ProgressionSelectionTargetType | None = None
    is_active: bool
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class AcademicLevelProgressionConfigureRequest(InputBase):
    progression_mode: AcademicLevelProgressionMode
    next_level_id: uuid.UUID | None = None
    selection_target_type: ProgressionSelectionTargetType | None = None
    target_level_ids: list[uuid.UUID] = Field(default_factory=list)
    target_classroom_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_progression_configuration(self):
        level_ids = self.target_level_ids
        classroom_ids = self.target_classroom_ids
        if len(level_ids) != len(set(level_ids)) or len(classroom_ids) != len(set(classroom_ids)):
            raise ValueError("student-selection destinations cannot contain duplicates")
        if self.progression_mode == AcademicLevelProgressionMode.DIRECT:
            if self.next_level_id is None:
                raise ValueError("direct progression requires next_level_id")
            if self.selection_target_type is not None or level_ids or classroom_ids:
                raise ValueError("direct progression cannot contain student-selection options")
        elif self.progression_mode == AcademicLevelProgressionMode.STUDENT_SELECTION:
            if self.next_level_id is not None:
                raise ValueError("student selection cannot contain next_level_id")
            if self.selection_target_type is None:
                raise ValueError("student selection requires selection_target_type")
            if self.selection_target_type == ProgressionSelectionTargetType.LEVEL:
                if not level_ids or classroom_ids:
                    raise ValueError("level selection requires only target_level_ids")
            elif not classroom_ids or level_ids:
                raise ValueError("classroom selection requires only target_classroom_ids")
        elif self.next_level_id is not None or self.selection_target_type is not None or level_ids or classroom_ids:
            raise ValueError("terminal progression cannot contain destinations")
        return self


class AcademicLevelProgressionResponse(OutputBase):
    academic_level_id: uuid.UUID
    academic_level_name: str
    next_level_id: uuid.UUID | None = None
    next_level_name: str | None = None
    progression_mode: AcademicLevelProgressionMode
    selection_target_type: ProgressionSelectionTargetType | None = None
    target_level_ids: list[uuid.UUID] = Field(default_factory=list)
    target_classroom_ids: list[uuid.UUID] = Field(default_factory=list)
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
