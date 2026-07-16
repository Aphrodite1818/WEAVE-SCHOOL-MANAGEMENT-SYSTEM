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
from app.modules.parents.models import (
    ParentAccountStatus,
    ParentInvitationStatus,
    ParentMembershipStatus,
)
from app.modules.students.models import ParentRelationship


PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9()\-\s]{5,28}[0-9]$")


class InputBase(BaseModel):
    """Base configuration for parent request schemas."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_to_lower=False,
        extra="forbid",
        use_enum_values=False,
        validate_assignment=True,
    )


class OutputBase(BaseModel):
    """Base configuration for parent response schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
    )


def clean_optional_string(value: str | None) -> str | None:
    """Trim optional strings and convert empty values to None."""

    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None


def clean_required_string(value: str) -> str:
    """Trim required strings and reject empty content."""

    cleaned = value.strip()
    if not cleaned:
        raise ValueError("value cannot be empty")
    return cleaned


def normalize_email(value: str) -> str:
    """Return the canonical email representation used by parent workflows."""

    return value.strip().casefold()


def normalize_phone_number(value: str | None) -> str | None:
    """Trim and validate an optional phone number."""

    cleaned = clean_optional_string(value)
    if cleaned is None:
        return None

    if not PHONE_PATTERN.fullmatch(cleaned):
        raise ValueError("phone number format is invalid")

    return cleaned


# ---------------------------------------------------------------------------
# Global ParentAccount requests
# ---------------------------------------------------------------------------


class ParentAccountRegisterRequest(InputBase):
    """
    Register a new global parent account.

    Registration creates login credentials only. It does not create a tenant
    membership or grant access to a student.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_parent_email(cls, value: EmailStr) -> str:
        """Normalize the global login email."""

        return normalize_email(str(value))

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Enforce the shared backend password baseline."""

        validate_password_strength(value)
        return value


class ParentAccountOnboardingRequest(InputBase):
    """Complete the minimum global parent profile after registration."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone_number: str | None = Field(default=None, max_length=30)
    occupation: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=500)
    emergency_phone: str | None = Field(default=None, max_length=30)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_required_fields(cls, value: str) -> str:
        """Clean required parent names."""

        return clean_required_string(value)

    @field_validator("occupation", "address", mode="before")
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        """Clean optional profile fields."""

        return clean_optional_string(value)

    @field_validator("phone_number", "emergency_phone", mode="before")
    @classmethod
    def validate_phone_fields(cls, value: str | None) -> str | None:
        """Clean and validate phone numbers."""

        return normalize_phone_number(value)


class ParentAccountProfileUpdateRequest(InputBase):
    """
    Parent-controlled global profile update.

    Email and password changes use dedicated authenticated flows.
    """

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone_number: str | None = Field(default=None, max_length=30)
    occupation: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=500)
    emergency_phone: str | None = Field(default=None, max_length=30)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_profile_names(cls, value: str | None) -> str | None:
        """Clean optional names while rejecting blank name updates."""

        if value is None:
            return None
        return clean_required_string(value)

    @field_validator("occupation", "address", mode="before")
    @classmethod
    def clean_profile_fields(cls, value: str | None) -> str | None:
        """Clean optional profile fields."""

        return clean_optional_string(value)

    @field_validator("phone_number", "emergency_phone", mode="before")
    @classmethod
    def validate_phone_fields(cls, value: str | None) -> str | None:
        """Clean and validate phone numbers."""

        return normalize_phone_number(value)

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "ParentAccountProfileUpdateRequest":
        """Reject empty update objects."""

        if not self.model_fields_set:
            raise ValueError("at least one profile field must be provided")
        return self


class ParentAccountPasswordChangeRequest(InputBase):
    """Authenticated parent password-change request."""

    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        """Enforce the shared backend password baseline."""

        validate_password_strength(value)
        return value

    @model_validator(mode="after")
    def validate_password_change(self) -> "ParentAccountPasswordChangeRequest":
        """Validate new-password confirmation and reuse."""

        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match")
        if self.current_password == self.new_password:
            raise ValueError("new_password must be different from current_password")
        return self


class ParentPasswordRequest(InputBase):
    """Start a global parent password-reset flow."""

    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_reset_email(cls, value: EmailStr) -> str:
        """Normalize the password-reset email."""

        return normalize_email(str(value))


class ParentPasswordResetConfirmRequest(InputBase):
    """Complete a global parent password-reset flow."""

    email: EmailStr
    reset_token: str = Field(min_length=20, max_length=500)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_reset_confirm_email(cls, value: EmailStr) -> str:
        """Normalize the password-reset email."""

        return normalize_email(str(value))

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        """Enforce the shared backend password baseline."""

        validate_password_strength(value)
        return value


# ---------------------------------------------------------------------------
# ParentAccount responses
# ---------------------------------------------------------------------------


class ParentAccountResponse(OutputBase):
    """Global parent account response."""

    id: uuid.UUID
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    occupation: str | None = None
    address: str | None = None
    emergency_phone: str | None = None
    account_status: ParentAccountStatus
    is_verified: bool
    is_active: bool
    profile_completed: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ParentAccountSummaryResponse(OutputBase):
    """Safe compact parent account profile."""

    id: uuid.UUID
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    is_verified: bool
    is_active: bool


# ---------------------------------------------------------------------------
# ParentMembership requests and responses
# ---------------------------------------------------------------------------


class ParentMembershipNotificationUpdateRequest(InputBase):
    """Parent-controlled school notification preferences."""

    receive_email_notifications: bool | None = None
    receive_push_notifications: bool | None = None

    @model_validator(mode="after")
    def require_notification_change(self) -> "ParentMembershipNotificationUpdateRequest":
        """Reject empty notification updates."""

        if not self.model_fields_set:
            raise ValueError("at least one notification preference must be provided")
        return self


class ParentMembershipEndRequest(InputBase):
    """Explicit privileged membership-ending request."""

    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        """Clean the required ending reason."""

        return clean_required_string(value)


class ParentMembershipReactivateRequest(InputBase):
    """Explicit membership reactivation request."""

    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        """Clean the required reactivation reason."""

        return clean_required_string(value)


class ParentMembershipResponse(OutputBase):
    """Tenant-specific parent membership response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    parent_account_id: uuid.UUID
    status: ParentMembershipStatus
    joined_at: datetime | None = None
    ended_at: datetime | None = None
    end_reason: str | None = None
    receive_email_notifications: bool
    receive_push_notifications: bool
    created_at: datetime
    updated_at: datetime


class ParentMembershipWithAccountResponse(ParentMembershipResponse):
    """Membership response containing a safe global profile."""

    parent_account: ParentAccountSummaryResponse


class ParentMembershipListResponse(OutputBase):
    """Tenant-scoped parent membership list."""

    items: list[ParentMembershipWithAccountResponse]
    total: int = Field(ge=0)


class ParentMembershipChoiceResponse(OutputBase):
    """One school option returned after global parent authentication."""

    membership_id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_logo_url: str | None = None
    membership_status: ParentMembershipStatus


class ParentMembershipChooserResponse(OutputBase):
    """Membership chooser returned when a parent belongs to several schools."""

    requires_membership_selection: Literal[True] = True
    parent_account_id: uuid.UUID
    memberships: list[ParentMembershipChoiceResponse]


class ParentMembershipSelectionRequest(InputBase):
    """Select one tenant membership after global authentication."""

    membership_id: uuid.UUID


# ---------------------------------------------------------------------------
# Parent invitations
# ---------------------------------------------------------------------------


class ParentInvitationCreateItem(InputBase):
    """One parent email supplied during student creation."""

    email: EmailStr
    relationship_type: ParentRelationship

    @field_validator("email", mode="after")
    @classmethod
    def normalize_invitation_email(cls, value: EmailStr) -> str:
        """Normalize the invitation email."""

        return normalize_email(str(value))


class ParentInvitationBatchCreateRequest(InputBase):
    """Optional parent invitations created with or after a student."""

    parents: list[ParentInvitationCreateItem] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def validate_unique_parent_emails(self) -> "ParentInvitationBatchCreateRequest":
        """Reject duplicate parent emails in one request."""

        emails = [item.email for item in self.parents]
        if len(emails) != len(set(emails)):
            raise ValueError("parent invitation emails must be unique")
        return self


class ParentInvitationCreateRequest(InputBase):
    """Create one invitation for an existing student."""

    student_id: uuid.UUID
    email: EmailStr
    relationship_type: ParentRelationship

    @field_validator("email", mode="after")
    @classmethod
    def normalize_invitation_email(cls, value: EmailStr) -> str:
        """Normalize the invitation email."""

        return normalize_email(str(value))


class ParentInvitationTokenRequest(InputBase):
    """Invitation token supplied by the invitation URL."""

    invitation_token: str = Field(min_length=20, max_length=500)


class ParentInvitationAcceptanceRequest(InputBase):
    """
    Accept an invitation after global parent authentication.

    Admission number is accepted only together with the invitation token.
    """

    invitation_token: str = Field(min_length=20, max_length=500)
    admission_number: str = Field(min_length=1, max_length=50)

    @field_validator("admission_number", mode="before")
    @classmethod
    def clean_admission_number(cls, value: str) -> str:
        """Clean admission-number input."""

        return clean_required_string(value)


class ParentInvitationRevokeRequest(InputBase):
    """Revoke a pending invitation."""

    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        """Clean the revocation reason."""

        return clean_required_string(value)


class ParentInvitationResponse(OutputBase):
    """Parent invitation response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    invited_email: EmailStr
    relationship_type: ParentRelationship
    admission_number_snapshot: str
    status: ParentInvitationStatus
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_by_admin_id: uuid.UUID | None = None
    accepted_by_parent_account_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ParentInvitationPublicContextResponse(OutputBase):
    """Safe invitation context shown before authentication."""

    invitation_id: uuid.UUID
    tenant_name: str
    tenant_logo_url: str | None = None
    student_display_name: str
    admission_number_hint: str
    relationship_type: ParentRelationship
    expires_at: datetime
    status: ParentInvitationStatus


class ParentInvitationListResponse(OutputBase):
    """Tenant invitation list."""

    items: list[ParentInvitationResponse]
    total: int = Field(ge=0)


class ParentOperationResponse(OutputBase):
    """Generic parent workflow result."""

    success: bool
    message: str


class ParentInvitationDispatchResponse(OutputBase):
    """Generic school-facing invitation response."""

    success: Literal[True] = True
    message: str = "Invitation processing started."
