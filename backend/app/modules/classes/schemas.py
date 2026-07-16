# ====================================== #
#              schemas.py                #
# ====================================== #

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.utils.normalization import (
    normalize_class_arm,
    normalize_class_name,
)


class InputBase(BaseModel):
    """Base schema for request payloads."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        str_to_lower=False,
        use_enum_values=False,
    )


class OutputBase(BaseModel):
    """Base schema for response payloads."""

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
    )


class ClassRoomBase(InputBase):
    """Shared classroom fields."""

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Class name e.g JSS1, JSS 1, Primary 4",
    )
    arm: str | None = Field(
        default=None,
        max_length=20,
        description="Optional class arm e.g A, B, Science",
    )
    teacher_id: uuid.UUID | None = Field(
        default=None,
        description="Optional class teacher ID",
    )

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Normalize class names to a canonical backend format."""

        normalized = normalize_class_name(value)
        if normalized is None:
            raise ValueError("class name cannot be empty")
        return normalized

    @field_validator("arm", mode="before")
    @classmethod
    def normalize_arm(cls, value: str | None) -> str | None:
        """Normalize optional class arms."""

        return normalize_class_arm(value)


class ClassRoomCreate(ClassRoomBase):
    """Payload for creating a classroom."""

    is_active: bool = Field(default=True, description="Whether the class is active")


class ClassRoomUpdate(InputBase):
    """Payload for updating ordinary classroom fields."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    arm: str | None = Field(default=None, max_length=20)
    teacher_id: uuid.UUID | None = Field(default=None)
    is_active: bool | None = Field(default=None)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        """Normalize class names to a canonical backend format."""

        if value is None:
            return None
        normalized = normalize_class_name(value)
        if normalized is None:
            raise ValueError("class name cannot be empty")
        return normalized

    @field_validator("arm", mode="before")
    @classmethod
    def normalize_arm(cls, value: str | None) -> str | None:
        """Normalize optional class arms."""

        return normalize_class_arm(value)


class ClassRoomResponse(OutputBase):
    """Classroom response schema."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    arm: str | None
    next_class_id: uuid.UUID | None
    is_terminal: bool
    teacher_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClassProgressionConfigureRequest(InputBase):
    """
    Configure explicit progression for one class.

    A non-terminal class may temporarily have no next class while the tenant is
    still configuring its progression chain. Session closure validation must
    reject that state when the class contains eligible students.
    """

    next_class_id: uuid.UUID | None = None
    is_terminal: bool = False

    @model_validator(mode="after")
    def validate_terminal_configuration(self) -> "ClassProgressionConfigureRequest":
        """A terminal class cannot have a next class."""

        if self.is_terminal and self.next_class_id is not None:
            raise ValueError("a terminal class cannot have next_class_id")
        return self


class ClassProgressionClearRequest(InputBase):
    """Clear progression configuration through an explicit operation."""

    confirmation: Literal["CLEAR_CLASS_PROGRESSION"]


class ClassProgressionResponse(OutputBase):
    """Configured progression for one class."""

    class_id: uuid.UUID
    class_name: str
    class_arm: str | None = None
    next_class_id: uuid.UUID | None = None
    next_class_name: str | None = None
    next_class_arm: str | None = None
    is_terminal: bool
    is_active: bool


class ClassProgressionValidationIssue(OutputBase):
    """One class-progression configuration issue."""

    class_id: uuid.UUID
    class_name: str
    code: Literal[
        "missing_next_class",
        "next_class_not_found",
        "next_class_inactive",
        "cross_tenant_target",
        "self_reference",
        "circular_chain",
        "terminal_has_next_class",
    ]
    message: str


class ClassProgressionValidationResponse(OutputBase):
    """Tenant class-progression validation result."""

    valid: bool
    issues: list[ClassProgressionValidationIssue]
