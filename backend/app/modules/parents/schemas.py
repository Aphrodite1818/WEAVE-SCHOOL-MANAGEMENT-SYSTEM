#==========================#
#     parent.schema.py     #
#==========================#

"""Refactored parent creation logic to be external and not tenant scoped again"""

from __future__ import annotations

import re
import uuid
from datetime import datetime 
from typing import Literal

from pydantic import(
    BaseModel, 
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator
)

from app.core.utils.validators import validate_password_strength
from app.modules.parents.models import(
    ParentAccountStatus,
    ParentInvitationStatus,
    ParentMembershipStatus
)

from app.modules.students.models import ParentRelationship


PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9()\-\s]{5,28}[0-9]$")


class InputBase(BaseModel):
    """Base class for request schemas"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_to_lower=False,
        extra="forbid",
        use_enum_values = False,
    )


class OutputBase(BaseModel):
    """Base class for response schemas"""

    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
        populate_by_name=True
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
    """
    Return the canonical email representation used by parent workflows.

    Pydantic validates the email format first. Services and repositories must
    use the same normalization before database lookup or insertion.
    """

    return value.strip().casefold()


def normalize_phone_number(value: str | None) -> str | None:
    """Trim and validate an optional phone number."""

    cleaned = clean_optional_string(value)

    if cleaned is None:
        return None

    if not PHONE_PATTERN.fullmatch(cleaned):
        raise ValueError("phone number format is invalid")

    return cleaned





#==========================#
#  Parent REQUEST SCHEMAS  #
#==========================#



class ParentAccountRegisterRequest(InputBase):
    """
    Register a new global parent account 

    Registration does not automatically grant access to a tenant or student
    Membership and student access are established through invation approval
    """


    email : EmailStr
    password : str = Field(min_length = 8 , max_length = 128)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_parent_email(cls , value : EmailStr) -> EmailStr:
        """Normalize the global login email"""

        return normalize_email(str(value))

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Enforce the shared backend password baseline."""

        validate_password_strength(value)
        return value



class ParentAccountOnboardingRequest(InputBase):
    """
    Schema used by the modal to collect additional parent information without
    making registration feel too complicated
    """

    first_name : str = Field(min_length = 3 , max_length = 100)
    last_name : str = Field(min_length = 3 , max_length = 100)
    phone_number : str | None = Field(default = None , max_length = 30)
    occupation : str | None = Field(default = None , max_length = 150)
    address : str | None = Field(default = None , max_length = 500)
    emergency_phone : str | None = Field(default = None ,max_length = 30)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def clean_required_fields(cls , value : str) -> str:
        """clean required parent names"""

        return clean_required_string(value)

    @field_validator("occupation", "address", mode="before")
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        """Clean optional modal profile fields."""

        return clean_optional_string(value)
    

    @field_validator("phone_number","emergency_phone", mode = "before")
    @classmethod
    def validate_phone_fields(cls , value : str | None) -> str | None:
        """clean and validate phone numbers"""

        return normalize_phone_number(value)
    




class ParentAccountProfileUpdateRequest(InputBase):
    """
    Parent-controlled global profile update

    Email and password changes require dedicated authenticated flows and are intentionally excluded
    """

    first_name : str | None = Field(min_length = 3 , max_length = 100 , default = None)
    last_name : str | None = Field(min_length = 3 , max_length = 100 , default = None)
    phone_number : str | None = Field(max_length = 30 , default= None)
    occupation : str | None = Field(max_length = 300 , default = None)
    address : str | None = Field(max_length = 300 , default= None)
    emergency_phone : str | None = Field(max_length = 30 , default = None)


    @field_validator(
        "first_name",
        "last_name",
        mode="before",
    )
    @classmethod
    def clean_profile_names(cls, value: str | None) -> str | None:
        """Clean optional names while rejecting blank name updates."""

        if value is None:
            return None

        return clean_required_string(value)

    @field_validator(
        "occupation",
        "address",
        mode="before",
    )
    @classmethod
    def clean_profile_fields(cls, value: str | None) -> str | None:
        """Clean optional profile fields."""

        return clean_optional_string(value)

    @field_validator(
        "phone_number",
        "emergency_phone",
        mode="before",
    )
    @classmethod
    def validate_phone_fields(cls, value: str | None) -> str | None:
        """Clean and validate phone numbers."""

        return normalize_phone_number(value)

    @model_validator(mode="after")
    def require_at_least_one_change(
        self,
    ) -> "ParentAccountProfileUpdateRequest":
        """Reject empty update objects."""

        if not self.model_fields_set:
            raise ValueError("at least one profile field must be provided")

        return self



class ParentAccountPasswordChangeRequest(InputBase):
    """Authenticated parent password-change request"""

    current_password : str = Field(min_length = 8 , max_length = 120)
    new_password : str = Field(min_length = 8 , max_length = 128)
    confirm_password : str = Field(min_length = 8 , max_length = 128)


    @model_validator(mode="after")
    def validate_password_change(
        self
    )->"ParentAccountPasswordChangeRequest":
        """Validate new-password confirmation and reuse"""

        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match")
        
        if self.current_password == self.new_password:
            raise ValueError(
                "new_password must be different from current_password"
            )

        validate_password_strength(self.new_password)
        
        return self
    


class ParentPasswordRequest(InputBase):
    """start a global parent password-reset flow"""

    email : EmailStr

    @field_validator("email", mode = "after")
    @classmethod
    def normalize_reset_email(cls , value : EmailStr) -> EmailStr:
        """Normalize the password-reset email"""

        return normalize_email(str(value))
    


class ParentPasswordResetConfirmRequest(InputBase):
    """Complete a global parent password-reset flow"""

    email : EmailStr
    reset_token : str = Field(min_length = 20 , max_length = 500)
    new_password : str = Field(min_length = 8 , max_length = 128)

    @field_validator("email", mode = "after")
    @classmethod
    def normalize_reset_confirm_email(cls , value : EmailStr) -> EmailStr:
        """Normalize the password-reset email."""

        return normalize_email(str(value))

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        """Enforce the shared backend password baseline."""

        validate_password_strength(value)
        return value





#==========================#
#  Parent RESPONSE SCHEMA  #
#==========================#


class ParentAccountResponse(OutputBase):
    """Global parent account Response"""
    id : uuid.UUID
    email : EmailStr
    first_name : str | None = None
    last_name : str | None = None
    phone_number : str | None = None
    occupation : str | None = None
    address : str | None = None
    emergency_phone : str | None = None
    account_status: ParentAccountStatus
    is_verified: bool
    is_active: bool
    profile_completed: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime



class ParentAccountSummaryResponse(OutputBase):
    """safe compact parent account profle"""
    id : uuid.UUID
    email : EmailStr 
    first_name : str | None = None
    last_name : str | None = None
    phone_number : str | None = None
    is_verified : bool 
    is_active : bool




#====================================================#
#      ParentMembership request and responses        #
#====================================================#

class ParentMembershipNotificationUpdateRequest(InputBase):
    """
    Parent-controlled school notification preferences

    Membership lifecycle status cannot be changed through this schema
    """

    receive_email_notifications : bool | None = None
    receive_push_notifications : bool | None = None


    @model_validator(mode = "after")
    def require_notification_change(
        self
    ) -> "ParentMembershipNotificationUpdateRequest":
        """Reject empty notification updates"""

        if not self.model_fields_set:
            raise ValueError(
                "at least one notification preference must be provided"
            )
        return self
    


class ParentMembershipEndRequest(InputBase):
    """
    Explicit privileged membership-ending request

    Normal lifecycle code should derive membership state from links. This 
    Schema is reserved for an explicit administrative or compliance action
    """

    reason : str = Field(min_length = 30, max_length = 500)

    @field_validator("reason" , mode = "before")
    @classmethod
    def clean_reason(cls , value : str) -> str:
        return clean_required_string(value)
    



class ParentMembershipReactivateRequest(InputBase):
    """
    Explicit membership reactivation request.

    Reactivation must only succeed where an approved usable student link is
    created or restored in the same service transaction.
    """

    reason: str = Field(min_length=3,max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        """Clean the required reactivation reason."""

        return clean_required_string(value)
    


class ParentMembershipResponse(OutputBase):
    id : uuid.UUID
    tenant_id : uuid.UUID
    parent_account_id : uuid.UUID
    status : ParentMembershipStatus
    joined_at : datetime | None = None
    ended_at : datetime |  None = None
    end_reason : str | None = None
    receive_email_notifications : bool
    receive_push_notifications : bool
    created_at : datetime
    updated_at : datetime





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





#==========================#
#   Parent Invitations     #
#==========================#


class ParentInvitationCreateItem(InputBase):
    """One parent email supplied during student creation"""

    email : EmailStr
    relationship_type : ParentRelationship


    @field_validator("email", mode = "after")
    @classmethod
    def normalize_invitation_email(cls, value : EmailStr ) -> str:
        """Normalize the invitation email"""
        return normalize_email(str(value))
    


class ParentInvitationBatchCreateRequest(InputBase):
    """
    Optional parent invitations created with or after a student.

    The agreed portal guardian limit starts at two. This schema allows no more
    than two invitation items during student creation.
    """

    parents: list[ParentInvitationCreateItem] = Field(
        default_factory=list,
        max_length=2,
    )

    @model_validator(mode="after")
    def validate_unique_parent_emails(
        self,
    ) -> "ParentInvitationBatchCreateRequest":
        """Reject duplicate parent emails in one request."""

        emails = [item.email for item in self.parents]

        if len(emails) != len(set(emails)):
            raise ValueError("parent invitation emails must be unique")

        return self
    



class ParentInvitationCreateRequest(InputBase):
    """Create one invitation for an existing student"""

    student_id : uuid.UUID
    email : EmailStr
    relationship_type : ParentRelationship 

    @field_validator("email" , mode = "after")
    @classmethod
    def normalize_invitation_email(cls , value : EmailStr) -> str:
        """Normalize the invitation email"""

        return normalize_email(str(value))
    



class ParentInvitationTokenRequest(InputBase):
    """Invitation token supplied by the invitation URL"""
    invitation_token : str = Field(min_length = 20 , max_length=500)



class ParentInvitationAcceptanceRequest(InputBase):
    """
    Accept an invitation after global parent authentication 

    Admission number is accepted only together with the invitation token
    The service must never perform a global admission-number lookup
    """


    invitation_token : str = Field(min_length = 20 , max_length = 500)
    admission_number : str = Field(min_length = 1 , max_length = 50)



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
    """
    Safe invitation context shown before authentication.

    It intentionally excludes whether a global parent account already exists.
    """

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


# ---------------------------------------------------------------------------
# Generic operation responses
# ---------------------------------------------------------------------------


class ParentOperationResponse(OutputBase):
    """Generic parent workflow result."""

    success: bool
    message: str


class ParentInvitationDispatchResponse(OutputBase):
    """
    Generic school-facing invitation response.

    This response deliberately does not reveal whether the invited email owns
    an existing global ParentAccount.
    """

    success: Literal[True] = True
    message: str = "Invitation processing started."
