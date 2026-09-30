"""Schemas for CBT AI question authoring and quota workflows."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.modules.cbt.ai.models import (
    AICreditReservationStatus,
    AIQuotaActorType,
    AIQuotaPurchaseStatus,
    AIQuotaRequestStatus,
)


MAX_QUESTION_PROMPT_LENGTH = 20_000
MAX_QUESTION_INSTRUCTION_LENGTH = 10_000
MAX_OPTION_TEXT_LENGTH = 10_000
MAX_OPTIONS_PER_QUESTION = 50

MAX_IMAGE_REQUIREMENT_LENGTH = 2_000
MAX_IMAGE_SEARCH_QUERY_LENGTH = 500
MAX_IMAGE_GENERATION_PROMPT_LENGTH = 2_000

MAX_QUOTA_ADMIN_NOTE_LENGTH = 2_000


AIVisualMode = Literal[
    "text_only",
    "auto",
]


class AIDraftBase(BaseModel):
    """
    Base configuration for untrusted AI-generated structured output.

    `extra="forbid"` is intentional. If the provider invents fields,
    validation must fail rather than silently discarding them.
    """

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )


class AIImageDirective(AIDraftBase):
    """
    Description of an image that must later be resolved by ImageResolver.

    This is NOT a final image asset and contains no local CBT asset ID.
    """

    requirement: str = Field(
        min_length=1,
        max_length=MAX_IMAGE_REQUIREMENT_LENGTH,
    )

    search_query: str = Field(
        min_length=1,
        max_length=MAX_IMAGE_SEARCH_QUERY_LENGTH,
    )

    generation_prompt: str | None = Field(
        default=None,
        max_length=MAX_IMAGE_GENERATION_PROMPT_LENGTH,
    )


class AIQuestionOptionDraft(AIDraftBase):
    """
    One generated answer option.

    An option may contain:
    - text only
    - an image only
    - both text and an image

    This mirrors the local CBT question-option model.
    """

    text: str | None = Field(
        default=None,
        max_length=MAX_OPTION_TEXT_LENGTH,
    )

    image: AIImageDirective | None = None

    is_correct: bool

    @model_validator(mode="after")
    def require_content(self) -> AIQuestionOptionDraft:
        if not self.text and self.image is None:
            raise ValueError(
                "An answer option must include text, an image, or both."
            )

        return self


class AIQuestionDraftBase(AIDraftBase):
    """Fields shared by every supported AI-generated CBT question."""

    prompt: str = Field(
        min_length=1,
        max_length=MAX_QUESTION_PROMPT_LENGTH,
    )

    instruction: str | None = Field(
        default=None,
        max_length=MAX_QUESTION_INSTRUCTION_LENGTH,
    )

    image: AIImageDirective | None = None

    options: list[AIQuestionOptionDraft] = Field(
        min_length=2,
        max_length=MAX_OPTIONS_PER_QUESTION,
    )

    @model_validator(mode="after")
    def validate_unique_options(self) -> AIQuestionDraftBase:
        identities: set[tuple] = set()

        for option in self.options:
            normalized_text = (
                " ".join(option.text.split()).casefold()
                if option.text
                else None
            )

            normalized_image = None

            if option.image is not None:
                normalized_image = (
                    " ".join(
                        option.image.requirement.split()
                    ).casefold(),
                    " ".join(
                        option.image.search_query.split()
                    ).casefold(),
                )

            identity = (
                normalized_text,
                normalized_image,
            )

            if identity in identities:
                raise ValueError(
                    "Question options must be unique."
                )

            identities.add(identity)

        return self


class AISingleChoiceQuestionDraft(AIQuestionDraftBase):
    """Generated single-answer choice question."""

    question_type: Literal["single_choice"]

    @model_validator(mode="after")
    def validate_correct_answer(
        self,
    ) -> AISingleChoiceQuestionDraft:
        correct_count = sum(
            1
            for option in self.options
            if option.is_correct
        )

        if correct_count != 1:
            raise ValueError(
                "A single-choice question must have exactly "
                "one correct option."
            )

        return self


class AIMultipleChoiceQuestionDraft(AIQuestionDraftBase):
    """Generated multiple-answer choice question."""

    question_type: Literal["multiple_choice"]

    @model_validator(mode="after")
    def validate_correct_answers(
        self,
    ) -> AIMultipleChoiceQuestionDraft:
        correct_count = sum(
            1
            for option in self.options
            if option.is_correct
        )

        if correct_count < 2:
            raise ValueError(
                "A multiple-choice question must have at least "
                "two correct options."
            )

        if correct_count == len(self.options):
            raise ValueError(
                "A multiple-choice question must contain at least "
                "one incorrect option."
            )

        return self


AIQuestionDraft = Annotated[
    AISingleChoiceQuestionDraft
    | AIMultipleChoiceQuestionDraft,
    Field(discriminator="question_type"),
]


class AIQuestionBatchDraft(AIDraftBase):
    """Validated batch returned from AI question generation."""

    questions: list[AIQuestionDraft] = Field(
        min_length=1,
    )


class AIRegeneratedQuestionDraft(AIDraftBase):
    """Validated envelope for targeted question regeneration."""

    question: AIQuestionDraft


# ============================================================================
# Quota API and service contracts
# ============================================================================


class AIQuotaSchemaBase(BaseModel):
    """Base configuration for quota request/response contracts."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


class AIQuotaRequestCreate(AIQuotaSchemaBase):
    """Teacher request for additional AI credits from the school reserve."""

    credits: int = Field(gt=0)


class AIQuotaRequestApprove(AIQuotaSchemaBase):
    """Admin approval payload for a pending teacher credit request."""

    approved_credits: int | None = Field(default=None, gt=0)
    note: str | None = Field(
        default=None,
        max_length=MAX_QUOTA_ADMIN_NOTE_LENGTH,
    )


class AIQuotaRequestReject(AIQuotaSchemaBase):
    """Admin rejection payload for a pending teacher credit request."""

    note: str | None = Field(
        default=None,
        max_length=MAX_QUOTA_ADMIN_NOTE_LENGTH,
    )


class AICreditAllocationCreate(AIQuotaSchemaBase):
    """Direct tenant-reserve allocation to a teacher or tenant admin."""

    recipient_actor_type: AIQuotaActorType
    recipient_actor_id: uuid.UUID
    credits: int = Field(gt=0)


class AIQuotaTopUpRequest(AIQuotaSchemaBase):
    """Tenant-admin intent to purchase additional tenant AI credits."""

    credits: int = Field(gt=0)


class AIWeeklyQuotaStatus(AIQuotaSchemaBase):
    week_start: date
    credit_limit: int = Field(ge=0)
    used_credits: int = Field(ge=0)
    reserved_credits: int = Field(ge=0)
    available_credits: int = Field(ge=0)


class AIExtraCreditStatus(AIQuotaSchemaBase):
    balance_credits: int = Field(ge=0)
    reserved_credits: int = Field(ge=0)
    available_credits: int = Field(ge=0)


class AIQuotaStatusResponse(AIQuotaSchemaBase):
    quota_account_id: uuid.UUID
    actor_type: AIQuotaActorType
    actor_id: uuid.UUID
    weekly: AIWeeklyQuotaStatus
    extra: AIExtraCreditStatus
    total_available_credits: int = Field(ge=0)


class AIQuotaRequestResponse(AIQuotaSchemaBase):
    id: uuid.UUID
    requester_quota_account_id: uuid.UUID
    requested_credits: int = Field(gt=0)
    approved_credits: int | None = Field(default=None, gt=0)
    status: AIQuotaRequestStatus
    reviewed_by_admin_id: uuid.UUID | None = None
    allocation_id: uuid.UUID | None = None
    admin_note: str | None = None
    requester_name: str | None = None
    requester_email: str | None = None
    reviewer_email: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    cancelled_at: datetime | None = None


class AIQuotaRequestListResponse(AIQuotaSchemaBase):
    items: list[AIQuotaRequestResponse]
    total: int = Field(ge=0)


class AIActorQuotaBalance(AIQuotaSchemaBase):
    quota_account_id: uuid.UUID
    actor_type: AIQuotaActorType
    actor_id: uuid.UUID
    display_name: str
    email: str | None = None
    weekly_available_credits: int = Field(ge=0)
    weekly_used_credits: int = Field(ge=0)
    extra_available_credits: int = Field(ge=0)
    total_available_credits: int = Field(ge=0)


class AIActorQuotaBalanceListResponse(AIQuotaSchemaBase):
    items: list[AIActorQuotaBalance]
    total: int = Field(ge=0)


class AITenantQuotaSummaryResponse(AIQuotaSchemaBase):
    tenant_reserve_credits: int = Field(ge=0)
    quota_actor_count: int = Field(ge=0)
    pending_request_count: int = Field(ge=0)
    personal_extra_balance_total: int = Field(ge=0)
    personal_extra_reserved_total: int = Field(ge=0)


class AICreditAllocationResponse(AIQuotaSchemaBase):
    id: uuid.UUID
    recipient_quota_account_id: uuid.UUID
    recipient_actor_type: AIQuotaActorType
    recipient_actor_id: uuid.UUID
    recipient_name: str | None = None
    recipient_email: str | None = None
    allocated_by_admin_id: uuid.UUID
    allocator_email: str | None = None
    credits: int = Field(gt=0)
    created_at: datetime


class AICreditAllocationListResponse(AIQuotaSchemaBase):
    items: list[AICreditAllocationResponse]
    total: int = Field(ge=0)


class AIQuotaPurchaseResponse(AIQuotaSchemaBase):
    id: uuid.UUID
    credits: int = Field(gt=0)
    amount_kobo: int = Field(gt=0)
    reference: str
    status: AIQuotaPurchaseStatus
    initiated_by_admin_id: uuid.UUID
    initiated_by_email: str | None = None
    created_at: datetime
    credited_at: datetime | None = None


class AIQuotaPurchaseListResponse(AIQuotaSchemaBase):
    items: list[AIQuotaPurchaseResponse]
    total: int = Field(ge=0)


class AICreditReservationResponse(AIQuotaSchemaBase):
    id: uuid.UUID
    quota_account_id: uuid.UUID
    status: AICreditReservationStatus
    reserved_free_credits: int = Field(ge=0)
    reserved_extra_credits: int = Field(ge=0)
    total_reserved_credits: int = Field(gt=0)
    expires_at: datetime


class AICreditSettlementResponse(AIQuotaSchemaBase):
    reservation_id: uuid.UUID
    settled_free_credits: int = Field(ge=0)
    settled_extra_credits: int = Field(ge=0)
    total_settled_credits: int = Field(ge=0)
    released_credits: int = Field(ge=0)
    settled_at: datetime
