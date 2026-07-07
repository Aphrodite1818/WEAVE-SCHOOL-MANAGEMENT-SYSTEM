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
    StudentAccessCodePurpose
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
    """Base input schema for student actor data."""

    admission_number: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    passport_photo_url: str | None = Field(default=None, max_length=500)
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
        "passport_photo_url",
        "state_of_origin",
        "arm",
        mode="before",
    )
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class StudentCreate(InputBase):
    """Schema for creating a student actor."""

    admission_number: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    passport_photo_url: str | None = Field(default=None, max_length=500)
    graduation_date: date | None = None
    class_id: uuid.UUID | None = None
    arm: str | None = Field(default=None, max_length=20)
    status: AcademicStatus = AcademicStatus.ACTIVE
    state_of_origin: str | None = Field(default=None, max_length=100)

    @field_validator(
        "admission_number",
        "first_name",
        "last_name",
        "passport_photo_url",
        "state_of_origin",
        "arm",
        mode="before",
    )
    @classmethod
    def clean_create_fields(cls, value: str | None) -> str | None:
        """Normalize optional student creation fields."""

        return _clean_optional_string(value)



class StudentUpdate(InputBase):
    """Schema for admin updating a student actor."""

    admission_number: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    passport_photo_url: str | None = Field(default=None, max_length=500)
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
        "passport_photo_url",
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
    passport_photo_url: str | None = Field(default=None, max_length=500)

    @field_validator("first_name", "last_name", "passport_photo_url", mode="before")
    @classmethod
    def clean_self_service_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class StudentOnboardingUpdate(InputBase):
    """Schema for student onboarding and self-service profile completion."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    gender: Gender
    passport_photo_url: str | None = Field(default=None, max_length=500)

    @field_validator("first_name", "last_name", "passport_photo_url", mode="before")
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

    setup_code : str | None = None
    access_code_expires_at : datetime | None = None



class StudentAdminAccessCodeResponse(OutputBase):
    """Response returned when an admin generates a  student access code"""
    
    student_id : uuid.UUID
    admission_number : str
    full_name : str | None = None
    purpose: StudentAccessCodePurpose
    access_code : str
    expires_at : datetime 




class StudentLoginProfile(OutputBase):
    """Compact student profile used after authentication."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    admission_number: str
    first_name: str | None = None
    last_name: str | None = None
    account_status: StudentAccountStatus
    is_verified: bool
    is_active: bool
    password_reset_required: bool


class StudentListResponse(OutputBase):
    """Paginated-style response container for student lists."""

    items: list[StudentResponse]
    total: int


class StudentParentLinkInputBase(InputBase):
    """Base input schema for linking a student to a parent."""

    student_id: uuid.UUID
    parent_id: uuid.UUID
    relationship_type: ParentRelationship = ParentRelationship.GUARDIAN
    is_primary_contact: bool = False
    receives_academic_updates: bool = True
    receives_fee_updates: bool = True


class StudentParentLinkCreate(StudentParentLinkInputBase):
    """Schema for creating a student-parent link."""


class StudentParentLinkUpdate(InputBase):
    """Schema for updating a student-parent link."""

    relationship_type: ParentRelationship | None = None
    is_primary_contact: bool | None = None
    receives_academic_updates: bool | None = None
    receives_fee_updates: bool | None = None


class StudentParentLinkParentSummary(OutputBase):
    """Compact parent summary attached to student-parent links."""

    id: uuid.UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None


class StudentParentLinkOutputBase(OutputBase):
    """Base output schema for a student-parent relationship."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    parent_id: uuid.UUID
    relationship_type: ParentRelationship
    is_primary_contact: bool
    receives_academic_updates: bool
    receives_fee_updates: bool
    created_at: datetime
    updated_at: datetime


class StudentParentLinkResponse(StudentParentLinkOutputBase):
    """Schema returned for a student-parent relationship."""

    parent: StudentParentLinkParentSummary | None = None


class StudentParentLinkListResponse(OutputBase):
    """Paginated-style response container for student-parent links."""

    items: list[StudentParentLinkResponse]
    total: int


class ParentLinkRequestParentSummary(OutputBase):
    """Compact parent summary attached to student link requests."""

    id: uuid.UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None


class ParentLinkRequestStudentSummary(OutputBase):
    """Compact student summary attached to parent link requests."""

    id: uuid.UUID
    admission_number: str
    first_name: str | None = None
    last_name: str | None = None


class StudentParentLinkRequestCreate(InputBase):
    """Parent request payload for linking a student by admission number."""

    admission_number: str = Field(..., min_length=1, max_length=50)
    relationship_type: ParentRelationship = ParentRelationship.GUARDIAN

    @field_validator("admission_number", mode="before")
    @classmethod
    def clean_admission_number(cls, value: str) -> str:
        """Normalize an admission number before lookup."""

        if not isinstance(value, str):
            return value
        return value.strip().upper()


class StudentParentLinkRequestRespond(InputBase):
    """Student response payload for a pending parent link request."""

    action: Literal["approve", "reject"]


class StudentParentLinkRequestResponse(OutputBase):
    """Pending or completed parent-student link request."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    parent_id: uuid.UUID
    admission_number_snapshot: str
    relationship_type: ParentRelationship
    status: StudentParentLinkRequestStatus
    requested_at: datetime
    responded_at: datetime | None = None
    parent: ParentLinkRequestParentSummary | None = None
    student: ParentLinkRequestStudentSummary | None = None


class StudentParentLinkRequestListResponse(OutputBase):
    """Paginated-style response container for parent link requests."""

    items: list[StudentParentLinkRequestResponse]
    total: int


class StudentLinkCodeInputBase(InputBase):
    """Base input schema for creating a student link code."""

    student_id: uuid.UUID
    max_use: int = Field(default=1, ge=1, le=5)


class StudentLinkCodeCreate(StudentLinkCodeInputBase):
    """Schema for generating a student link code."""


class StudentLinkCodeRedeem(InputBase):
    """Schema for a parent linking themselves to a student with a code."""

    code: str = Field(min_length=4, max_length=80)
    relationship_type: ParentRelationship = ParentRelationship.GUARDIAN
    is_primary_contact: bool = False
    receives_academic_updates: bool = True
    receives_fee_updates: bool = True

    @field_validator("code", mode="before")
    @classmethod
    def clean_code(cls, value: str) -> str:
        """Normalize a pairing code before lookup."""

        if not isinstance(value, str):
            return value
        return value.strip().upper()


class StudentLinkCodeOutputBase(OutputBase):
    """Base output schema for student link code data."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    code: str
    expires_at: datetime
    used_at: datetime | None = None
    max_use: int
    use_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StudentLinkCodeResponse(StudentLinkCodeOutputBase):
    """Schema returned after generating a student link code."""


class StudentOnboardingStatusResponse(OutputBase):
    """Student onboarding status response."""

    actor_type: Literal["student"]
    student_id: uuid.UUID
    onboarding_required: bool
    profile_status: StudentProfileStatus
    completion_target: Literal["student"]
    required_fields: list[str]
    current_values: dict[str, Any]


class StudentChangePasswordRequest(InputBase):
    """Student password change payload."""

    current_password: str = Field(..., min_length=1, max_length=64)
    new_password: str = Field(..., min_length=8, max_length=64)
    confirm_password: str = Field(..., min_length=8, max_length=64)
