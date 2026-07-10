# ====================================== #
#              schemas.py                #
# ====================================== #

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.utils.normalization import (
    clean_string,
    normalize_class_arm,
    normalize_class_level,
    normalize_class_name,
)


class InputBase(BaseModel):
    """Base schema for request payloads."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        str_to_lower=False,
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

    level: str | None = Field(
        default=None,
        max_length=100,
        description="Academic level e.g Junior Secondary School 1, Senior Secondary School 2",
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

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, value: str | None) -> str | None:
        """Validate and normalize optional class level text."""

        if value is None or clean_string(value) is None:
            return None

        normalized = normalize_class_level(value)
        if normalized is None:
            raise ValueError(
                "class level can only contain letters, numbers, spaces, hyphens, slashes, ampersands, or parentheses"
            )
        return normalized


class ClassRoomCreate(ClassRoomBase):
    """Payload for creating a classroom."""

    pass


class ClassRoomUpdate(InputBase):
    """Payload for updating a classroom."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    level: str | None = Field(
        default=None,
        max_length=100,
    )

    arm: str | None = Field(
        default=None,
        max_length=20,
    )

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

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, value: str | None) -> str | None:
        """Validate and normalize optional class level text."""

        if value is None or clean_string(value) is None:
            return None

        normalized = normalize_class_level(value)
        if normalized is None:
            raise ValueError(
                "class level can only contain letters, numbers, spaces, hyphens, slashes, ampersands, or parentheses"
            )
        return normalized


class ClassRoomResponse(OutputBase):
    """Classroom response schema."""

    id: uuid.UUID
    tenant_id: uuid.UUID

    name: str
    level: str | None
    arm: str | None

    teacher_id: uuid.UUID | None
    is_active: bool

    created_at: datetime
    updated_at: datetime
