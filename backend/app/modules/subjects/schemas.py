import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

class InputBase(BaseModel):
    """Base for all request/input schemas."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_to_lower=False,
        extra="forbid",
    )


class OutputBase(BaseModel):
    """Base for all response/output schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


def _clean_optional_string(value: str | None) -> str | None:
    """Internal helper for clean optional string."""

    if value is None:
        return None

    cleaned_value = value.strip()
    return cleaned_value or None


class SubjectCreate(InputBase):
    """Pydantic schema for the subjects domain."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="name of the subject",
        examples=["Mathematics"],
    )
    code: str | None = Field(
        default=None,
        max_length=30,
        examples=["MATH"],
        description="short code for subject",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        examples=["core mathematics subject for junior class"],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Validate name."""

        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("name cannot be empty")

        return cleaned_value

    @field_validator("code", "description", mode="before")
    @classmethod
    def clean_optional_text_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class SubjectUpdate(InputBase):
    """Pydantic schema for the subjects domain."""

    name: str | None = Field(default=None, min_length=2, max_length=100)
    code: str | None = Field(default=None, min_length=2, max_length=30)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        """Normalize name."""

        cleaned_value = _clean_optional_string(value)

        if cleaned_value is not None and len(cleaned_value) < 2:
            raise ValueError("name must be at least 2 characters long")

        return cleaned_value

    @field_validator("code", "description", mode="before")
    @classmethod
    def clean_optional_text_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class SubjectStatusUpdate(InputBase):
    """Pydantic schema for the subjects domain."""

    is_active: bool


class SubjectArchiveRequest(InputBase):
    confirmation: Literal["ARCHIVE_SUBJECT"]


class SubjectRestoreRequest(InputBase):
    confirmation: Literal["RESTORE_SUBJECT"]


class SubjectTeacherResponse(OutputBase):
    """Teacher summary inside subject responses."""

    teacher_id: uuid.UUID = Field(validation_alias="id")
    email: str
    first_name: str | None
    last_name: str | None
    staff_id: str | None


class SubjectResponse(OutputBase):
    """Pydantic schema for the subjects domain."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    code: str | None
    description: str | None
    is_active: bool
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    teachers: list[SubjectTeacherResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SubjectListResponse(OutputBase):
    """Pydantic schema for the subjects domain."""

    items: list[SubjectResponse]
    total: int
