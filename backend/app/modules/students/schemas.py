import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.students.models import (
    AcademicStatus,
    Gender,
    ParentRelationship,
    StudentAccountStatus,
    StudentParentLinkRequestStatus,
    StudentProfileStatus,
    StudentAccessCodePurpose,
)


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
    """Normalize optional string input."""

    if value is None:
        return None

    cleaned_value = value.strip()
    return cleaned_value or None


class StudentInputBase(InputBase):
    """Base input schema for student actor data.

    Media URLs are intentionally excluded. Passport photos are managed only by
    the dedicated media upload endpoints.
    """

    admission_number: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    graduation_date: date | None = None
    class_id: uuid.UUID | None = None
    arm: str | None = Field(default=None, max_length=20)
    status: AcademicStatus = AcademicStatus.ACTIVE
    account_status: StudentAccountStatus = StudentAccountStatus.ACTIVE
    is_verified: bool = False
    is_active: bool = True
    last_login_at: datetime | None = None
    state_of_origin: str | None = Field(default=None, max_length=100)

    @field_validator(
        "admission_number",
        "first_name",
        "last_name",
        "state_of_origin",
        "arm",
        mode="before",
    )
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class StudentCreate(InputBase):
    """Schema for creating a student actor.

    Passport media is uploaded separately after the student exists.
    """

    admission_number: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    graduation_date: date | None = None
    class_id: uuid.UUID | None = None
    arm: str | None = Field(default=None, max_length=20)
    status: AcademicStatus = AcademicStatus.ACTIVE
    state_of_origin: str | None = Field(default=None, max_length=100)

    @field_validator(
        "admission_number",
        "first_name",
        "last_name",
        "state_of_origin",
        "arm",
        mode="before",
    )
    @classmethod
    def clean_create_fields(cls, value: str | None) -> str | None:
        """Normalize optional student creation fields."""

        return _clean_optional_string(value)


class StudentUpdate(InputBase):
    """Schema for admin updating a student actor.

    Passport media is changed through the media endpoint, not profile updates.
    """

    admission_number: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    graduation_date: date | None = None
    class_id: uuid.UUID | None = None
    arm: str | None = Field(default=None, max_length=20)
    status: AcademicStatus | None = None
    profile_status: StudentProfileStatus | None = None
    account_status: StudentAccountStatus | None = None
    is_verified: bool | None = None
    is_active: bool | None = None
    password_reset_required: bool | None = None
    last_login_at: datetime | None = None
    state_of_origin: str | None = Field(default=None, max_length=100)

    @field_validator(
        "admission_number",
        "first_name",
        "last_name",
        "state_of_origin",
        "arm",
        mode="before",
    )
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class StudentSelfUpdate(InputBase):
    """Schema for a student updating their own profile fields."""

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    gender: Gender | None = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_self_service_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class StudentOnboardingUpdate(InputBase):
    """Schema for student onboarding and self-service profile completion."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    gender: Gender

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_onboarding_fields(cls, value: str | None) -> str | None:
        """Normalize student onboarding fields."""

        return _clean_optional_string(value)


class StudentOutputBase(OutputBase):
    """Base output schema for student actor data."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    admission_number: str
    first_name: str | None = None
    last_name: str | None = None
    account_status: StudentAccountStatus
    is_verified: bool
    is_active: bool
    password_reset_required: bool
    last_login_at: datetime | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    passport_photo_url: str | None = None
    admission_date: date
    graduation_date: date | None = None
    class_id: uuid.UUID | None = None
    arm: str | None = None
    status: AcademicStatus
    profile_status: StudentProfileStatus
    created_at: datetime
    updated_at: datetime
    state_of_origin: str | None = None


class StudentResponse(StudentOutputBase):
    """Schema returned for student profile data."""

    setup_code: str | None = None
    access_code_expires_at: datetime | None = None


class StudentAdminAccessCodeResponse(OutputBase):
    """Response returned when an admin generates a student access code."""

    student_id: uuid.UUID
    admission_number: str
    full_name: str | None = None
    purpose: StudentAccessCodePurpose
    access_code: str
    expires_at: datetime


class StudentChangePasswordRequest(InputBase):
    """Student first-login/password-reset password change payload."""

    access_code: str = Field(..., min_length=1, max_length=32)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class StudentOnboardingStatusResponse(OutputBase):
    """Student onboarding state returned to the frontend."""

    password_reset_required: bool
    profile_status: StudentProfileStatus
    onboarding_complete: bool


class StudentLinkCodeCreate(InputBase):
    expires_in_minutes: int = Field(default=30, ge=5, le=1440)


class StudentLinkCodeResponse(OutputBase):
    code: str
    expires_at: datetime


class StudentLinkCodeRedeem(InputBase):
    code: str = Field(..., min_length=1, max_length=255)
    relationship: ParentRelationship = ParentRelationship.GUARDIAN
    is_primary: bool = False
    can_view_results: bool = True
    can_view_attendance: bool = True
    can_receive_notifications: bool = True


class StudentParentLinkCreate(InputBase):
    student_id: uuid.UUID
    parent_id: uuid.UUID
    relationship: ParentRelationship = ParentRelationship.GUARDIAN
    is_primary: bool = False
    can_view_results: bool = True
    can_view_attendance: bool = True
    can_receive_notifications: bool = True


class StudentParentLinkUpdate(InputBase):
    relationship: ParentRelationship | None = None
    is_primary: bool | None = None
    can_view_results: bool | None = None
    can_view_attendance: bool | None = None
    can_receive_notifications: bool | None = None


class StudentParentLinkResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    parent_id: uuid.UUID
    relationship: ParentRelationship
    is_primary: bool
    can_view_results: bool
    can_view_attendance: bool
    can_receive_notifications: bool
    created_at: datetime
    updated_at: datetime


class StudentParentLinkRequestCreate(InputBase):
    student_id: uuid.UUID
    message: str | None = Field(default=None, max_length=500)


class StudentParentLinkRequestRespond(InputBase):
    action: Literal["approve", "reject"]
    relationship: ParentRelationship = ParentRelationship.GUARDIAN
    is_primary: bool = False
    can_view_results: bool = True
    can_view_attendance: bool = True
    can_receive_notifications: bool = True


class StudentParentLinkRequestResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    parent_id: uuid.UUID
    status: StudentParentLinkRequestStatus
    message: str | None = None
    responded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StudentParentLinkRequestListResponse(OutputBase):
    items: list[StudentParentLinkRequestResponse]
    total: int
