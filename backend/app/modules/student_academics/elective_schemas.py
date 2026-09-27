from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ElectiveOutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ElectiveGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    minimum_choices: int = Field(default=0, ge=0)
    maximum_choices: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("name cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_choice_bounds(self) -> "ElectiveGroupCreate":
        if self.minimum_choices > self.maximum_choices:
            raise ValueError("minimum_choices cannot exceed maximum_choices")
        return self


class ElectiveGroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    minimum_choices: int | None = Field(default=None, ge=0)
    maximum_choices: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("name cannot be blank")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> "ElectiveGroupUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one elective group field must be provided")
        return self


class ElectiveGroupResponse(ElectiveOutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    curriculum_id: uuid.UUID
    name: str
    minimum_choices: int
    maximum_choices: int
    lifecycle: str
    created_at: datetime
    updated_at: datetime


class StudentElectiveSubjectOption(ElectiveOutputBase):
    curriculum_subject_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
    subject_code: str | None = None
    selected: bool = False


class StudentElectiveGroupWorkspace(ElectiveOutputBase):
    elective_group_id: uuid.UUID
    name: str
    minimum_choices: int
    maximum_choices: int
    selected_count: int
    locked: bool
    locked_reason: str | None = None
    subjects: list[StudentElectiveSubjectOption] = Field(default_factory=list)


class StudentElectiveWorkspaceResponse(ElectiveOutputBase):
    academic_session_id: uuid.UUID | None = None
    academic_session_name: str | None = None
    academic_term_id: uuid.UUID | None = None
    academic_term_name: str | None = None
    academic_level_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None
    groups: list[StudentElectiveGroupWorkspace] = Field(default_factory=list)


class StudentElectiveSelectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_subject_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("curriculum_subject_ids")
    @classmethod
    def unique_subjects(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise ValueError("elective subject selections must be unique")
        return value
