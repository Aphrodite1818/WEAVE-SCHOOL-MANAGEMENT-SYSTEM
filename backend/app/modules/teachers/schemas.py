# ====================================== #
#          teachers/schemas.py           #
# ====================================== #

"""Teacher request and response schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.teachers.models import TeacherAccountStatus, TeacherStatus


class InputBase(BaseModel):
    """Base for all request/input schemas."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_to_lower=False,
        extra="forbid",
        use_enum_values=True,
    )


class OutputBase(BaseModel):
    """Base for all response/output schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
    )


def _clean_optional_string(value: str | None) -> str | None:
    """Trim optional strings and convert empty strings to None."""

    if value is None:
        return None

    cleaned_value = value.strip()
    return cleaned_value or None


class TeacherCreate(InputBase):
    """Schema for creating a teacher actor."""

    email: EmailStr
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    staff_id: str | None = Field(default=None, max_length=50)
    qualification: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=150)

    @field_validator(
        "first_name",
        "last_name",
        "staff_id",
        "qualification",
        "specialization",
        mode="before",
    )
    @classmethod
    def clean_optional_text_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class TeacherUpdate(InputBase):
    """Schema for admin updating a teacher actor."""

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=64)

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    staff_id: str | None = Field(default=None, max_length=50)
    qualification: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=150)

    account_status: TeacherAccountStatus | None = None
    status: TeacherStatus | None = None
    is_verified: bool | None = None
    is_active: bool | None = None

    @field_validator(
        "first_name",
        "last_name",
        "staff_id",
        "qualification",
        "specialization",
        mode="before",
    )
    @classmethod
    def clean_optional_text_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class TeacherSelfUpdate(InputBase):
    """Self-update schema teacher profile update schema."""

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    staff_id: str | None = Field(default=None, max_length=50)
    qualification: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=150)

    @field_validator(
        "first_name",
        "last_name",
        "staff_id",
        "qualification",
        "specialization",
        mode="before",
    )
    @classmethod
    def clean_optional_self_service_text_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class TeacherOnboardingUpdate(InputBase):
    """Schema for teacher onboarding and self-service profile completion."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    qualification: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=150)

    @field_validator(
        "first_name",
        "last_name",
        "qualification",
        "specialization",
        mode="before",
    )
    @classmethod
    def clean_onboarding_fields(cls, value: str | None) -> str | None:
        """Normalize onboarding text fields."""

        return _clean_optional_string(value)


class SubjectSummaryResponse(OutputBase):
    """Short subject response used inside teacher responses."""

    id: uuid.UUID
    name: str
    code: str | None


class TeacherResponse(OutputBase):
    """Teacher response schema."""

    id: uuid.UUID
    tenant_id: uuid.UUID

    email: EmailStr
    first_name: str | None
    last_name: str | None

    staff_id: str | None
    qualification: str | None
    specialization: str | None

    account_status: TeacherAccountStatus
    status: TeacherStatus
    profile_completed: bool
    is_verified: bool
    is_active: bool
    last_login_at: datetime | None

    subjects: list[SubjectSummaryResponse] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime


    passport_photo_url : str | None = None


class TeacherLoginProfile(OutputBase):
    """Compact teacher profile used after authentication."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    account_status: TeacherAccountStatus
    status: TeacherStatus
    is_verified: bool
    is_active: bool
    passport_photo_url : str | None


class TeacherListResponse(OutputBase):
    """Paginated teacher list response."""

    items: list[TeacherResponse]
    total: int


class TeacherOnboardingStatusResponse(OutputBase):
    """Teacher onboarding status response."""

    actor_type: Literal["teacher"]
    teacher_id: uuid.UUID
    onboarding_required: bool
    profile_completed: bool
    completion_target: Literal["teacher"]
    required_fields: list[str]
    current_values: dict[str, Any]
