# ====================================== #
#     tenant_management/schemas.py       #
# ====================================== #

"""Tenant management request and response schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    computed_field,
    field_validator,
)

from app.core.utils.validators import generate_slug
from app.tenant_management.models import (
    InstitutionType,
    SubscriptionPlan,
    TenantStatus,
    TenantVerificationStatus,
)

PHONE_PATTERN = r"^\+?[1-9]\d{7,14}$"


# ──────────────────────────────────────────────
# SHARED BASE CONFIGS
# ──────────────────────────────────────────────


class InputBase(BaseModel):
    """Base class for tenant request schemas."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_to_lower=False,
        extra="forbid",
    )


class OutputBase(BaseModel):
    """Base class for tenant response schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
        frozen=True,
    )


# ──────────────────────────────────────────────
# SHARED HELPERS
# ──────────────────────────────────────────────


def _clean_optional_string(value: str | None) -> str | None:
    """Trim optional string fields and convert empty strings to None."""

    if value is None:
        return None

    cleaned_value = value.strip()
    return cleaned_value or None


# ──────────────────────────────────────────────
# BASE TENANT SCHEMAS
# ──────────────────────────────────────────────


class TenantBase(InputBase):
    """Shared tenant/school profile fields."""

    school_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        examples=["GreenField Academy Lagos"],
    )
    email: EmailStr
    phone: str | None = Field(
        default=None,
        pattern=PHONE_PATTERN,
        examples=["+23470123457688"],
    )
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str = Field(default="Nigeria", max_length=100)
    timezone: str = Field(default="Africa/Lagos", max_length=50)
    language: str = Field(default="en", max_length=10)
    admission_number_prefix: str | None = Field(
        default=None,
        min_length=2,
        max_length=20,
    )

    @field_validator("school_name")
    @classmethod
    def validate_school_name(cls, value: str) -> str:
        """Validate and clean school name."""

        if not value.strip():
            raise ValueError("school_name cannot be empty")
        return value.strip()

    @field_validator(
        "phone",
        "address",
        "city",
        "state",
        "country",
        "timezone",
        "language",
        "admission_number_prefix",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, value: str | None) -> str | None:
        """Clean optional tenant text fields."""

        return _clean_optional_string(value)

    @field_validator("admission_number_prefix")
    @classmethod
    def normalize_admission_number_prefix(cls, value: str | None) -> str | None:
        """Uppercase admission number prefix when provided."""

        if value is None:
            return None
        return value.upper()


# ──────────────────────────────────────────────
# REQUEST SCHEMAS
# ──────────────────────────────────────────────


class TenantRegisterRequest(InputBase):
    """Public tenant registration request.

    Registration accepts only the school name, workspace email, and initial
    tenant-admin password. The tenant slug is generated internally and the
    admission-number prefix is collected during onboarding.
    """

    school_name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        examples=["GreenField Academy Lagos"],
    )
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="Initial tenant administrator password",
    )
    initial_plan_intent: SubscriptionPlan | None = Field(
        default=None,
        description="Preferred first-term plan; this never grants access or starts payment.",
    )

    @field_validator("school_name")
    @classmethod
    def validate_school_name(cls, value: str) -> str:
        """Validate and clean school name."""

        if not value.strip():
            raise ValueError("school_name cannot be empty")
        return value.strip()


class TenantCreate(TenantBase):
    """Schema for internal tenant creation."""

    school_bot_whatssap_number: str | None = Field(
        default=None,
        pattern=PHONE_PATTERN,
        description="The WhatsApp number the school bot listens on",
    )
    plan: SubscriptionPlan = SubscriptionPlan.FREE_TRIAL
    max_students: int = Field(default=500, ge=1, le=100_000)
    max_teachers: int = Field(default=50, ge=1, le=100_000)

    @field_validator("school_bot_whatssap_number", mode="before")
    @classmethod
    def clean_school_bot_whatssap_number(cls, value: str | None) -> str | None:
        """Clean optional school bot WhatsApp number."""

        return _clean_optional_string(value)

    @computed_field
    @property
    def log_slug_preview(self) -> str:
        """Return generated slug preview without persisting it."""

        return generate_slug(self.school_name)


class TenantUpdate(InputBase):
    """Schema for general tenant/school profile updates."""

    school_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=50)
    language: str | None = Field(default=None, max_length=10)
    institution_type: InstitutionType | None = None
    admission_number_prefix: str | None = Field(
        default=None,
        min_length=2,
        max_length=20,
    )
    school_bot_whatssap_number: str | None = Field(
        default=None,
        pattern=PHONE_PATTERN,
        description="The WhatsApp number the school bot listens on",
    )

    @field_validator(
        "school_name",
        "phone",
        "address",
        "city",
        "state",
        "country",
        "timezone",
        "language",
        "admission_number_prefix",
        "school_bot_whatssap_number",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, value: str | None) -> str | None:
        """Clean optional update text fields."""

        return _clean_optional_string(value)

    @field_validator("admission_number_prefix")
    @classmethod
    def normalize_update_admission_number_prefix(
        cls,
        value: str | None,
    ) -> str | None:
        """Uppercase admission number prefix when provided."""

        if value is None:
            return None
        return value.upper()


class TenantOnboardingUpdate(InputBase):
    """Schema for first-time tenant onboarding completion."""

    admission_number_prefix: str = Field(
        ...,
        min_length=2,
        max_length=20,
    )
    institution_type: InstitutionType
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    address: str = Field(..., min_length=3, max_length=500)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    country: str = Field(default="Nigeria", max_length=100)
    timezone: str = Field(default="Africa/Lagos", max_length=50)
    language: str = Field(default="en", max_length=10)
    school_bot_whatssap_number: str | None = Field(
        default=None,
        pattern=PHONE_PATTERN,
        description="The WhatsApp number the school bot listens on",
    )

    @field_validator(
        "phone",
        "admission_number_prefix",
        "address",
        "city",
        "state",
        "country",
        "timezone",
        "language",
        "school_bot_whatssap_number",
        mode="before",
    )
    @classmethod
    def clean_text_fields(cls, value: str | None) -> str | None:
        """Clean onboarding text fields."""

        return _clean_optional_string(value)

    @field_validator("admission_number_prefix")
    @classmethod
    def normalize_onboarding_admission_number_prefix(
        cls,
        value: str,
    ) -> str:
        """Uppercase the onboarding admission prefix."""

        return value.upper()


class TenantStatusUpdate(InputBase):
    """Schema for changing tenant status."""

    status: TenantStatus
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Reason why the tenant status update is happening",
    )

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        """Clean optional status update reason."""

        return _clean_optional_string(value)


# ──────────────────────────────────────────────
# RESPONSE SCHEMAS
# ──────────────────────────────────────────────


class TenantPublicResponse(OutputBase):
    """Public tenant response schema."""

    id: uuid.UUID
    school_name: str
    slug: str
    admission_number_prefix: str | None
    email: EmailStr | None
    phone: str | None
    address: str | None
    city: str | None
    state: str | None
    country: str
    logo_url: str | None
    school_bot_whatssap_number: str | None
    status: TenantStatus
    plan: SubscriptionPlan
    timezone: str
    language: str
    onboarding_completed: bool
    institution_type: InstitutionType | None = None
    verification_status: TenantVerificationStatus
    created_at: datetime
    updated_at: datetime


class TenantManagementResponse(TenantPublicResponse):
    """Detailed tenant response schema for tenant/admin management."""

    max_students: int
    max_teachers: int
    feature_flags: dict[str, Any] | None
    trial_ends_at: datetime | None
    subscription_ends_at: datetime | None
    is_deleted: bool
    deleted_at: datetime | None


class TenantContext(OutputBase):
    """Tenant context used by authenticated tenant actors."""

    id: uuid.UUID
    slug: str
    school_name: str
    status: TenantStatus
    verification_status: TenantVerificationStatus
    plan: SubscriptionPlan
    timezone: str
    language: str
    whatsapp_number: str | None
    max_students: int
    max_teachers: int
    feature_flags: dict[str, Any] | None
    onboarding_completed: bool
    institution_type: InstitutionType | None = None

    @property
    def is_active(self) -> bool:
        """Return whether tenant is active."""

        return self.status == TenantStatus.ACTIVE

    @property
    def is_verified(self) -> bool:
        """Return whether tenant is verified."""

        return self.verification_status == TenantVerificationStatus.ACTIVE

    @property
    def whatsapp_enabled(self) -> bool:
        """Return whether WhatsApp bot is enabled."""

        return bool(self.feature_flags and self.feature_flags.get("whatsapp_bot"))


class TenantOnboardingStatusResponse(OutputBase):
    """Tenant-admin onboarding status response."""

    actor_type: Literal["tenant_admin"]
    tenant_id: uuid.UUID
    onboarding_required: bool
    onboarding_completed: bool
    completion_target: Literal["tenant"]
    required_fields: list[str]
    current_values: dict[str, Any]
