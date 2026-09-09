from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.utils.normalization import normalize_class_name
from app.core.utils.validators import validate_password_strength
from app.modules.parents.models import ParentMembershipStatus
from app.modules.students.models import (
    AcademicStatus,
    Gender,
    ParentLinkVerifiedByType,
    ParentRelationship,
    StudentAccessCodePurpose,
    StudentAccountStatus,
    StudentEnrollmentOutcome,
    StudentParentLinkRequestStatus,
    StudentParentLinkStatus,
    StudentProfileStatus,
)

_PATCH_NULL_ERROR = "cannot be null; omit the field to leave the current value unchanged"


class InputBase(BaseModel):
    """Base configuration for student request schemas."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=False,
        validate_assignment=True,
    )


class OutputBase(BaseModel):
    """Base configuration for student response schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
    )

    @field_validator("class_name", mode="before", check_fields=False)
    @classmethod
    def normalize_response_class_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_class_name(value) or value


def clean_optional_string(value: str | None) -> str | None:
    """Trim optional strings and convert blanks to None."""

    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None


def clean_required_string(value: str) -> str:
    """Trim required strings and reject blank content."""

    cleaned = value.strip()
    if not cleaned:
        raise ValueError("value cannot be empty")
    return cleaned


def normalize_email(value: str) -> str:
    """Normalize email input for invitation matching."""

    return value.strip().casefold()


def validate_date_before_today(
    value: date | None,
    *,
    field_name: str,
) -> date | None:
    """Reject today and future dates where a historical date is required."""

    if value is not None and value >= date.today():
        raise ValueError(f"{field_name} must be before today")
    return value


def validate_date_not_future(
    value: date | None,
    *,
    field_name: str,
) -> date | None:
    """Reject future dates while permitting today."""

    if value is not None and value > date.today():
        raise ValueError(f"{field_name} cannot be in the future")
    return value


# ---------------------------------------------------------------------------
# Student creation and safe profile updates
# ---------------------------------------------------------------------------


class StudentParentInvitationInput(InputBase):
    """Optional parent invitation supplied during student creation."""

    email: EmailStr
    relationship_type: ParentRelationship

    @field_validator("email", mode="after")
    @classmethod
    def normalize_parent_email(cls, value: EmailStr) -> str:
        """Normalize invitation email."""

        return normalize_email(str(value))


class StudentCreate(InputBase):
    """
    Create a student using backend-generated admission credentials.

    Admission numbers are generated internally and are never accepted from a
    client. Academic level is authoritative; class placement is optional.
    """

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    academic_level_id: uuid.UUID
    class_id: uuid.UUID | None = None
    gender: Gender | None = None
    state_of_origin: str | None = Field(default=None, max_length=100)
    parents: list[StudentParentInvitationInput] = Field(
        default_factory=list,
        max_length=2,
    )

    @field_validator("state_of_origin", mode="before")
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        """Clean optional student fields."""

        return clean_optional_string(value)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_required_names(cls, value: str) -> str:
        """Clean required student names."""

        return clean_required_string(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        """Require a date of birth before today."""

        validated = validate_date_before_today(
            value,
            field_name="date_of_birth",
        )
        assert validated is not None
        return validated

    @model_validator(mode="after")
    def validate_parent_invitations(self) -> "StudentCreate":
        """Reject duplicate parent invitation emails."""

        emails = [parent.email for parent in self.parents]
        if len(emails) != len(set(emails)):
            raise ValueError("parent invitation emails must be unique")
        return self


class StudentAdminProfileUpdate(InputBase):
    """
    Safe tenant-admin profile update.

    Admission number, lifecycle state, current class, authentication state,
    archival fields, and graduation fields are intentionally excluded.
    """

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    state_of_origin: str | None = Field(default=None, max_length=100)

    @field_validator(
        "first_name",
        "last_name",
        "state_of_origin",
        mode="before",
    )
    @classmethod
    def clean_fields(cls, value: str | None) -> str | None:
        """Clean profile fields."""

        return clean_optional_string(value)

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        """Require any supplied date of birth to be before today."""

        return validate_date_before_today(
            value,
            field_name="date_of_birth",
        )

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "StudentAdminProfileUpdate":
        """Reject empty profile updates."""

        if not self.model_fields_set:
            raise ValueError("at least one student field must be provided")
        return self


class StudentSelfUpdate(InputBase):
    """Student-controlled partial profile update."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    gender: Gender | None = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_names(cls, value: str | None) -> str | None:
        """Clean student profile names."""

        return clean_optional_string(value)

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "StudentSelfUpdate":
        """Reject empty updates and explicit nulls for required profile fields."""

        if not self.model_fields_set:
            raise ValueError("at least one profile field must be provided")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} {_PATCH_NULL_ERROR}")
        return self


class StudentOnboardingUpdate(InputBase):
    """Complete required student profile fields."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    gender: Gender

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_names(cls, value: str) -> str:
        """Clean required onboarding names."""

        return clean_required_string(value)


# ---------------------------------------------------------------------------
# Student lifecycle requests
# ---------------------------------------------------------------------------


class StudentLifecycleReasonRequest(InputBase):
    """Base lifecycle request requiring a recorded reason."""

    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        """Clean lifecycle reason."""

        return clean_required_string(value)


class StudentSuspendRequest(StudentLifecycleReasonRequest):
    """Suspend a student without closing current enrolment."""

    promotion_hold: bool = False


class StudentReinstateRequest(StudentLifecycleReasonRequest):
    """Reinstate a suspended student."""


class StudentWithdrawRequest(StudentLifecycleReasonRequest):
    """Withdraw a student and close their current enrolment."""


class StudentExpelRequest(StudentLifecycleReasonRequest):
    """Expel a student and immediately end parent access."""


class StudentGraduateRequest(StudentLifecycleReasonRequest):
    """Privileged single-student graduation correction request."""


class StudentArchiveRequest(StudentLifecycleReasonRequest):
    """Archive a student without destroying historical records."""


class StudentRestoreFromArchiveRequest(StudentLifecycleReasonRequest):
    """Restore an archived record to operational visibility."""


class StudentReturnEnrollmentRequest(StudentLifecycleReasonRequest):
    """Create a new placement after a genuine terminal student exit."""

    target_academic_level_id: uuid.UUID
    target_class_id: uuid.UUID
    academic_session_id: uuid.UUID
    effective_date: date = Field(default_factory=date.today)



class StudentPromotionHoldUpdateRequest(InputBase):
    """Set or remove an individual progression hold."""

    promotion_hold: bool
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        """Clean the hold reason."""

        return clean_required_string(value)


class StudentHardDeleteRequest(InputBase):
    """Explicit hard-delete request for an accidental unused record."""

    confirmation: Literal["DELETE_UNUSED_STUDENT"]
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        """Clean the hard-delete reason."""

        return clean_required_string(value)


# ---------------------------------------------------------------------------
# Student enrolment responses
# ---------------------------------------------------------------------------


class StudentEnrollmentResponse(OutputBase):
    """Immutable student class-placement segment."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    academic_level_id: uuid.UUID
    class_id: uuid.UUID | None = None
    academic_session_id: uuid.UUID
    started_on: date
    ended_on: date | None = None
    entry_outcome: StudentEnrollmentOutcome
    exit_outcome: StudentEnrollmentOutcome | None = None
    entry_reason: str | None = None
    exit_reason: str | None = None
    created_by_admin_id: uuid.UUID | None = None
    ended_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class StudentEnrollmentDetailResponse(StudentEnrollmentResponse):
    """Enrollment segment with display labels."""

    class_name: str | None = None
    class_arm: str | None = None
    academic_level_name: str | None = None
    academic_session_name: str | None = None
    lifecycle_state: Literal["historical", "current", "upcoming"] = "historical"


class StudentEnrollmentListResponse(OutputBase):
    """Student enrollment history list."""

    items: list[StudentEnrollmentDetailResponse]
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Student access-code requests
# ---------------------------------------------------------------------------


class StudentAccessCodeGenerateRequest(InputBase):
    """Generate a new student access code."""

    purpose: StudentAccessCodePurpose


class StudentAdminAccessCodeResponse(OutputBase):
    """One-time access-code response returned to an administrator."""

    student_id: uuid.UUID
    admission_number: str
    full_name: str | None = None
    purpose: StudentAccessCodePurpose
    access_code: str
    expires_at: datetime


class StudentChangePasswordRequest(InputBase):
    """Student access-code password setup/reset request."""

    access_code: str = Field(min_length=1, max_length=32)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        """Enforce the shared backend password baseline."""

        validate_password_strength(value)
        return value

    @model_validator(mode="after")
    def validate_password_confirmation(self) -> "StudentChangePasswordRequest":
        """Require matching password values."""

        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match")
        return self


# ---------------------------------------------------------------------------
# Parent-child linking and approval
# ---------------------------------------------------------------------------


class StudentParentLinkRequestCreate(InputBase):
    """Create an approval request from a valid invitation."""

    invitation_token: str = Field(min_length=20, max_length=500)
    admission_number: str = Field(min_length=1, max_length=50)

    @field_validator("admission_number", mode="before")
    @classmethod
    def clean_admission_number(cls, value: str) -> str:
        """Clean admission-number input."""

        return clean_required_string(value)


class StudentParentLinkRequestDecision(InputBase):
    """Approve or reject one parent-child link request."""

    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_optional_reason(cls, value: str | None) -> str | None:
        """Clean an optional decision reason."""

        return clean_optional_string(value)

    @model_validator(mode="after")
    def validate_decision_reason(self) -> "StudentParentLinkRequestDecision":
        """Require a reason for rejection."""

        if self.action == "reject" and not self.reason:
            raise ValueError("reason is required when rejecting a request")
        return self


class StudentParentLinkUpdateRequest(InputBase):
    """Update non-lifecycle link preferences."""

    relationship_type: ParentRelationship | None = None
    is_primary_contact: bool | None = None
    receives_academic_updates: bool | None = None
    receives_fee_updates: bool | None = None

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "StudentParentLinkUpdateRequest":
        """Reject empty updates and explicit null preference values."""

        if not self.model_fields_set:
            raise ValueError("at least one link field must be provided")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} {_PATCH_NULL_ERROR}")
        return self


class StudentParentLinkEndRequest(InputBase):
    """Explicitly end one parent-child relationship."""

    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        """Clean the ending reason."""

        return clean_required_string(value)


class StudentParentLinkReactivateRequest(InputBase):
    """Explicitly reactivate a previously ended parent link."""

    reason: str = Field(min_length=3, max_length=500)
    is_primary_contact: bool = False
    receives_academic_updates: bool = True
    receives_fee_updates: bool = True

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        """Clean reactivation reason."""

        return clean_required_string(value)


class StudentParentLinkResponse(OutputBase):
    """Verified parent-child link response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    parent_membership_id: uuid.UUID
    relationship_type: ParentRelationship
    status: StudentParentLinkStatus
    is_primary_contact: bool
    receives_academic_updates: bool
    receives_fee_updates: bool
    verified_at: datetime
    verified_by_type: ParentLinkVerifiedByType
    verified_by_id: uuid.UUID | None = None
    ended_at: datetime | None = None
    end_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class StudentParentLinkDetailResponse(StudentParentLinkResponse):
    """Parent-child link response with parent display fields."""

    parent_account_id: uuid.UUID
    parent_first_name: str | None = None
    parent_last_name: str | None = None
    parent_email: EmailStr
    membership_status: ParentMembershipStatus


class StudentParentLinkListResponse(OutputBase):
    """Student parent-link list response."""

    items: list[StudentParentLinkDetailResponse]
    total: int = Field(ge=0)


class StudentParentLinkRequestResponse(OutputBase):
    """Parent-child approval request response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    invitation_id: uuid.UUID
    student_id: uuid.UUID
    parent_account_id: uuid.UUID
    parent_membership_id: uuid.UUID | None = None
    admission_number_snapshot: str
    relationship_type: ParentRelationship
    status: StudentParentLinkRequestStatus
    requested_at: datetime
    responded_at: datetime | None = None
    responded_by_type: ParentLinkVerifiedByType | None = None
    responded_by_id: uuid.UUID | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class StudentParentLinkRequestDetailResponse(StudentParentLinkRequestResponse):
    """Link request with safe parent and student display values."""

    parent_email: EmailStr
    parent_first_name: str | None = None
    parent_last_name: str | None = None
    student_name: str | None = None


class StudentParentLinkRequestListResponse(OutputBase):
    """Parent-child approval request list."""

    items: list[StudentParentLinkRequestDetailResponse]
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Student responses
# ---------------------------------------------------------------------------


class StudentLifecycleCapabilities(OutputBase):
    """Backend-owned lifecycle actions available for the student's current state."""

    can_undo_withdrawal: bool = False
    can_undo_expulsion: bool = False
    can_undo_graduation: bool = False
    can_readmit: bool = False
    can_reinstate_expelled: bool = False
    can_reenrol_graduate: bool = False
    undo_block_reason: str | None = None


class StudentOutputBase(OutputBase):
    """Student profile and lifecycle response."""

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
    academic_level_id: uuid.UUID | None = None
    status: AcademicStatus
    promotion_hold: bool
    profile_status: StudentProfileStatus
    state_of_origin: str | None = None
    is_archived: bool
    archived_at: datetime | None = None
    archived_by_admin_id: uuid.UUID | None = None
    archive_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    lifecycle_capabilities: StudentLifecycleCapabilities | None = None


class StudentResponse(StudentOutputBase):
    """Student response with optional creation credentials."""

    setup_code: str | None = None
    access_code_expires_at: datetime | None = None


class StudentDetailResponse(StudentResponse):
    """Student response with current class display information."""

    class_name: str | None = None
    class_arm: str | None = None
    academic_level_name: str | None = None
    current_enrollment_id: uuid.UUID | None = None
    upcoming_enrollment: StudentEnrollmentDetailResponse | None = None
    current_academic_session_id: uuid.UUID | None = None
    current_academic_session_name: str | None = None
    current_academic_term_id: uuid.UUID | None = None
    current_academic_term_name: str | None = None


class StudentListResponse(OutputBase):
    """Student list response."""

    items: list[StudentDetailResponse]
    total: int = Field(ge=0)


class StudentLifecycleTransitionResponse(OutputBase):
    """Response returned after a student lifecycle transition."""

    student: StudentDetailResponse
    previous_status: AcademicStatus
    new_status: AcademicStatus
    session_revoked: bool
    access_codes_revoked: int = Field(ge=0)
    affected_parent_links: int = Field(ge=0)
    membership_recalculations: int = Field(ge=0)


class StudentOnboardingStatusResponse(OutputBase):
    """Student onboarding state."""

    actor_type: Literal["student"]
    student_id: uuid.UUID
    onboarding_required: bool
    profile_status: StudentProfileStatus
    completion_target: Literal["student"]
    required_fields: list[str]
    current_values: dict[str, Any]


class StudentHardDeleteEligibilityResponse(OutputBase):
    """Hard-delete dependency inspection result."""

    student_id: uuid.UUID
    eligible: bool
    blocking_dependencies: list[str]
    recommendation: Literal["hard_delete", "archive"]
    academic_level_name: str | None = None
