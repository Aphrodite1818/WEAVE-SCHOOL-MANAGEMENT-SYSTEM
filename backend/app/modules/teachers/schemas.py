"""Teacher account, membership, invitation, and assignment schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.utils.validators import validate_password_strength
from app.modules.teachers.models import (
    TeacherAccountStatus,
    TeacherInvitationStatus,
    TeacherMembershipStatus,
)

PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9()\-\s]{5,28}[0-9]$")


class InputBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, use_enum_values=False
    )


class OutputBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, use_enum_values=True, populate_by_name=True
    )


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_email(value: str) -> str:
    return value.strip().casefold()


class TeacherAccountRegisterRequest(InputBase):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_teacher_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class TeacherAccountOnboardingRequest(InputBase):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone_number: str | None = Field(default=None, max_length=30)
    qualification: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=150)

    @field_validator(
        "first_name", "last_name", "qualification", "specialization", mode="before"
    )
    @classmethod
    def clean_fields(cls, value: str | None) -> str | None:
        return clean_optional(value)

    @field_validator("phone_number", mode="before")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        cleaned = clean_optional(value)
        if cleaned is not None and not PHONE_PATTERN.fullmatch(cleaned):
            raise ValueError("phone number format is invalid")
        return cleaned


class TeacherAccountProfileUpdateRequest(InputBase):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone_number: str | None = Field(default=None, max_length=30)
    qualification: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("at least one teacher profile field must be provided")
        return self


class TeacherPasswordChangeRequest(InputBase):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_change(self):
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match")
        if self.current_password == self.new_password:
            raise ValueError("new_password must differ from current_password")
        validate_password_strength(self.new_password)
        return self


class TeacherInvitationCreateRequest(InputBase):
    email: EmailStr
    job_title: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    employment_type: str | None = Field(default=None, max_length=50)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_invited_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))


class TeacherInvitationAcceptanceRequest(InputBase):
    invitation_token: str = Field(min_length=20, max_length=500)


class TeacherInvitationRevokeRequest(InputBase):
    reason: str = Field(min_length=3, max_length=500)


class TeacherMembershipUpdateRequest(InputBase):
    job_title: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    employment_type: str | None = Field(default=None, max_length=50)
    receive_email_notifications: bool | None = None
    receive_push_notifications: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("at least one membership field must be provided")
        return self


class TeacherMembershipSuspendRequest(InputBase):
    reason: str = Field(min_length=3, max_length=500)


class TeacherMembershipEndRequest(InputBase):
    reason: str = Field(min_length=3, max_length=500)


class TeacherMembershipReactivateRequest(InputBase):
    reason: str = Field(min_length=3, max_length=500)


class TeacherMembershipSubjectUpdateRequest(InputBase):
    subject_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_subjects(self):
        if len(self.subject_ids) != len(set(self.subject_ids)):
            raise ValueError("subject_ids must be unique")
        return self


class TeacherAccountResponse(OutputBase):
    id: uuid.UUID
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    qualification: str | None = None
    specialization: str | None = None
    passport_photo_url: str | None = None
    account_status: TeacherAccountStatus
    is_verified: bool
    is_active: bool
    profile_completed: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TeacherMembershipResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    teacher_account_id: uuid.UUID
    staff_id: str | None = None
    job_title: str | None = None
    department: str | None = None
    employment_type: str | None = None
    status: TeacherMembershipStatus
    joined_at: datetime
    ended_at: datetime | None = None
    end_reason: str | None = None
    receive_email_notifications: bool
    receive_push_notifications: bool
    created_at: datetime
    updated_at: datetime


class TeacherMembershipWithAccountResponse(TeacherMembershipResponse):
    teacher_account: TeacherAccountResponse


class TeacherMembershipListResponse(OutputBase):
    items: list[TeacherMembershipWithAccountResponse]
    total: int = Field(ge=0)


class TeacherMembershipChoiceResponse(OutputBase):
    membership_id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_logo_url: str | None = None
    membership_status: TeacherMembershipStatus


class TeacherMembershipChooserResponse(OutputBase):
    requires_membership_selection: Literal[True] = True
    teacher_account_id: uuid.UUID
    memberships: list[TeacherMembershipChoiceResponse]


class TeacherMembershipSelectionRequest(InputBase):
    membership_id: uuid.UUID


class TeacherInvitationResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    invited_email: EmailStr
    staff_id: str | None = None
    job_title: str | None = None
    department: str | None = None
    employment_type: str | None = None
    status: TeacherInvitationStatus
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_by_admin_id: uuid.UUID | None = None
    accepted_by_teacher_account_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class TeacherInvitationPublicContextResponse(OutputBase):
    invitation_id: uuid.UUID
    tenant_name: str
    tenant_logo_url: str | None = None
    invited_email: EmailStr
    staff_id: str | None = None
    job_title: str | None = None
    department: str | None = None
    employment_type: str | None = None
    expires_at: datetime
    status: TeacherInvitationStatus
    recommended_action: Literal["login", "register", "contact_school"]


class TeacherInvitationDispatchResponse(OutputBase):
    success: Literal[True] = True
    message: str = "Invitation processing started."


# ---------------------------------------------------------------------------
# Legacy tenant-teacher compatibility schemas
# ---------------------------------------------------------------------------


class TeacherCreate(TeacherAccountOnboardingRequest):
    """Compatibility request for legacy tenant-teacher creation imports."""

    email: EmailStr
    staff_id: str | None = Field(default=None, max_length=50)


class TeacherUpdate(TeacherAccountProfileUpdateRequest):
    """Compatibility request for legacy tenant-teacher update imports."""

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    account_status: TeacherAccountStatus | None = None
    is_active: bool | None = None


TeacherSelfUpdate = TeacherAccountProfileUpdateRequest
TeacherOnboardingUpdate = TeacherAccountProfileUpdateRequest
TeacherResponse = TeacherAccountResponse


class TeacherListResponse(OutputBase):
    items: list[TeacherResponse]
    total: int = Field(ge=0)


class TeacherOnboardingStatusResponse(OutputBase):
    actor_type: str
    teacher_id: uuid.UUID | None = None
    teacher_account_id: uuid.UUID | None = None
    onboarding_required: bool
    profile_completed: bool
    completion_target: str
    required_fields: list[str] = Field(default_factory=list)
    current_values: dict = Field(default_factory=dict)
