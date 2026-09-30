"""Database models for CBT AI quota , usage and credit accounting"""

from __future__ import annotations

from typing import Any
from datetime import datetime
import uuid
from enum import Enum as PyEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    CheckConstraint,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    DateTime,
    Text,
    String,
)

from sqlalchemy.dialects.postgresql import UUID
from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


def enum_values(enum_cls: type[PyEnum]) -> list[str]:
    return [item.value for item in enum_cls]


class AIQuotaActorType(str, PyEnum):
    """Actor types that can own and consume CBT AI credits"""

    TEACHER = "teacher"
    TENANT_ADMIN = "tenant_admin"


class AICreditReservationStatus(str, PyEnum):
    """Lifecycle states for an AI credit reservation"""

    PENDING = "pending"
    SETTLED = "settled"
    RELEASED = "released"
    EXPIRED = "expired"


class AIQuotaRequestStatus(str, PyEnum):
    """Lifecycle of a teacher AI credit request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AIQuotaPurchaseStatus(str, PyEnum):
    """Lifecycle of a tenant AI credit purchase."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AICreditLedgerBucket(str, PyEnum):
    """Credit bucket affected by a ledger entry."""

    WEEKLY_FREE = "weekly_free"
    TOP_UP = "top_up"
    TENANT_RESERVE = "tenant_reserve"


class AICreditLedgerEventType(str, PyEnum):
    """Actual credit movements recorded by the AI accounting system."""

    PURCHASE = "purchase"
    ALLOCATION_OUT = "allocation_out"
    ALLOCATION_IN = "allocation_in"
    CONSUMPTION = "consumption"
    ADJUSTMENT = "adjustment"


class AIQuotaAccount(BaseModel):
    """
    Canonical AI-credit identity for ont tenant actor

    Teacher and tenant admins live in different database tables.
    This model gives the AI quota subsystem one common identity to
    reference for:

    -Weekly free credits
    -personal extra credits
    -reservations
    -quota requests
    -allocations
    -usage ledger entries

    Exactly one actor reference must be populated
    """

    __tablename__ = "cbt_ai_quota_accounts"

    actor_type: Mapped[AIQuotaActorType] = mapped_column(
        SQLEnum(
            AIQuotaActorType,
            name="ai_quota_actor_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values(),
        ),
        nullable=False,
    )

    teacher_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.teacher_memberships.id", ondelete="CASCADE"),
        nullable=True,
    )

    tenant_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.tenant_admins.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            """
            (
                actor_type = 'teacher'
                AND teacher_membership_id IS NOT NULL
                AND tenant_admin_id IS NULL
            )
            OR
            (
                actor_type = 'tenant_admin'
                AND tenant_admin_id IS NOT NULL
                AND teacher_membership_id IS NULL
            )
            """,
            name="ck_cbt_ai_quota_accounts_actor_consistency",
        ),
        Index(
            "uq_cbt_ai_quota_accounts_teacher",
            "teacher_membership_id",
            unique=True,
            postgresql_where=(teacher_membership_id.is_not(None)),
        ),
        Index(
            "uq_cbt_ai_quota_accounts_tenant_admin",
            "tenant_admin_id",
            unique=True,
            postgresql_where=(tenant_admin_id.is_not(None)),
        ),
        Index(
            "ix_cbt_ai_quota_accounts_tenant_actor_type",
            "tenant_id",
            "actor_type",
        ),
    )


class AIWeeklyQuota(BaseModel):
    """
    Weekly free-credit bucket for one AI quota account

    A new row is created per quota account per week

    Example:
        quota_account_id = teacher/admin AI account
        weekly_start = 2026-09-28
        credit_limit = 100
        used_credits = 35
        reserved_credits  = 10


    Available credits:
        credit_limit - used_credits - reserved_credits
    """

    __tablename__ = "cbt_ai_weekly_quota"

    quota_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.cbt_ai_quota_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    week_start: Mapped[datetime] = mapped_column(nullable=False)

    credit_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )

    used_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    reserved_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    __table_args__ = (
        UniqueConstraint(
            "quota_account_id",
            "week_start",
            name="uq_cbt_ai_weekly_quotas_account_week",
        ),
        CheckConstraint(
            "credit_limit >= 0",
            name="ck_cbt_ai_weekly_quotas_limit_nonnegative",
        ),
        CheckConstraint(
            "used_credits >= 0",
            name="ck_cbt_ai_weekly_quotas_used_nonnegative",
        ),
        CheckConstraint(
            "reserved_credits >= 0",
            name="ck_cbt_ai_weekly_quotas_reserved_nonnegative",
        ),
        CheckConstraint(
            "used_credits + reserved_credits <= credit_limit",
            name="ck_cbt_ai_weekly_quotas_capacity",
        ),
        Index(
            "ix_cbt_ai_weekly_quotas_tenant_week",
            "tenant_id",
            "week_start",
        ),
        Index(
            "ix_cbt_ai_weekly_quotas_account_week",
            "quota_account_id",
            "week_start",
        ),
    )


class AIExtraCreditBalance(BaseModel):
    """
    Persistent personal extra-credit balance for one AI quota account.

    These credits are allocated from the tenant-wide reserve and do not
    reset weekly.

    Available credits:
        available_credits - reserved_credits
    """

    __tablename__ = "cbt_ai_extra_credit_balances"

    quota_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_ai_quota_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    available_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    reserved_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    __table_args__ = (
        UniqueConstraint(
            "quota_account_id",
            name="uq_cbt_ai_extra_credit_balances_account",
        ),
        CheckConstraint(
            "available_credits >= 0",
            name="ck_cbt_ai_extra_credit_balances_available_nonnegative",
        ),
        CheckConstraint(
            "reserved_credits >= 0",
            name="ck_cbt_ai_extra_credit_balances_reserved_nonnegative",
        ),
        CheckConstraint(
            "reserved_credits <= available_credits",
            name="ck_cbt_ai_extra_credit_balances_reserved_capacity",
        ),
        Index(
            "ix_cbt_ai_extra_credit_balances_tenant",
            "tenant_id",
        ),
    )


class AITenantCreditBalance(BaseModel):
    """
    Tenant-wide reserve of purchased AI credits.

    These credits belong to the school itself and are not consumed
    directly by generation requests.

    They are allocated by a tenant admin into individual
    AIExtraCreditBalance records.
    """

    __tablename__ = "cbt_ai_tenant_credit_balances"

    available_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            name="uq_cbt_ai_tenant_credit_balances_tenant",
        ),
        CheckConstraint(
            "available_credits >= 0",
            name="ck_cbt_ai_tenant_credit_balances_nonnegative",
        ),
    )


class AICreditReservation(BaseModel):
    """
    Durable hold placed on AI credits before an external provider call

    A reservation may draw from:
    -the actor's currently weelky free quota
    -the actor's personal extra-credit balance

    The reservation is later either:
    -settled against actual usage
    - released when unused
    - expired and recovered if the request dies
    """

    __tablename__ = "cbt_ai_credit_reservations"

    quota_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.cbt_ai_quota_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    weekly_quota_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.cbt_ai_weekly_quotas.id", ondelete="SET NULL"),
        nullable=True,
    )

    reserved_free_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    reserved_extra_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    settled_free_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    settled_extra_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    status: Mapped[AICreditReservationStatus] = mapped_column(
        SQLEnum(
            AICreditReservationStatus,
            name="cbt_ai_credit_reservation_status",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=AICreditReservationStatus.PENDING,
        server_default=AICreditReservationStatus.PENDING.value,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "reserved_free_credits >= 0",
            name="ck_cbt_ai_credit_reservations_reserved_free_nonnegative",
        ),
        CheckConstraint(
            "reserved_extra_credits >= 0",
            name="ck_cbt_ai_credit_reservations_reserved_extra_nonnegative",
        ),
        CheckConstraint(
            """
            reserved_free_credits + reserved_extra_credits > 0
            """,
            name="ck_cbt_ai_credit_reservations_positive_total",
        ),
        CheckConstraint(
            "settled_free_credits >= 0",
            name="ck_cbt_ai_credit_reservations_settled_free_nonnegative",
        ),
        CheckConstraint(
            "settled_extra_credits >= 0",
            name="ck_cbt_ai_credit_reservations_settled_extra_nonnegative",
        ),
        CheckConstraint(
            """
            settled_free_credits <= reserved_free_credits
            """,
            name="ck_cbt_ai_credit_reservations_settled_free_capacity",
        ),
        CheckConstraint(
            """
            settled_extra_credits <= reserved_extra_credits
            """,
            name="ck_cbt_ai_credit_reservations_settled_extra_capacity",
        ),
        CheckConstraint(
            """
            (
                status = 'pending'
                AND settled_at IS NULL
                AND released_at IS NULL
            )
            OR
            (
                status = 'settled'
                AND settled_at IS NOT NULL
            )
            OR
            (
                status IN ('released', 'expired')
                AND released_at IS NOT NULL
            )
            """,
            name="ck_cbt_ai_credit_reservations_status_consistency",
        ),
        Index(
            "ix_cbt_ai_credit_reservations_account_status",
            "quota_account_id",
            "status",
        ),
        Index(
            "ix_cbt_ai_credit_reservations_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_cbt_ai_credit_reservations_pending_expiry",
            "expires_at",
            postgresql_where=(status == AICreditReservationStatus.PENDING),
        ),
    )


class AICreditAllocation(BaseModel):
    """
    Records an allocation of tenant-owned AI credits to an individual
    AI quota account

    Examples:
        School reserve:5,000 credits
        Admin allocated: 200 credits
        Teacher top-up balance: +200
        School reserve: -200

    This table is the permanent audit record of that transfer
    """

    __tablename__ = "cbt_ai_credit_allocations"

    recipient_quota_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_ai_quota_accounts.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    allocated_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.tenant_admins.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "credits > 0",
            name="ck_cbt_ai_credit_allocations_positive_credits",
        ),
        Index(
            "ix_cbt_ai_credit_allocations_recipient",
            "recipient_quota_account_id",
        ),
        Index(
            "ix_cbt_ai_credit_allocations_admin",
            "allocated_by_admin_id",
        ),
        Index(
            "ix_cbt_ai_credit_allocations_tenant_created",
            "tenant_id",
            "created_at",
        ),
    )


class AIQuotaRequest(BaseModel):
    """
    A request by a teacher for additional AI credits from the school's
    tenant-wide credit reserve.

    Approval does not create new credits. It transfers already-owned
    tenant credits into the teacher's personal top-up balance.
    """

    __tablename__ = "cbt_ai_quota_requests"

    requester_quota_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_ai_quota_accounts.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    requested_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[AIQuotaRequestStatus] = mapped_column(
        SQLEnum(
            AIQuotaRequestStatus,
            name="cbt_ai_quota_request_status",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=AIQuotaRequestStatus.PENDING,
        server_default=AIQuotaRequestStatus.PENDING.value,
    )

    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.tenant_admins.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    approved_credits: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    allocation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_ai_credit_allocations.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    admin_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "requested_credits > 0",
            name="ck_cbt_ai_quota_requests_requested_positive",
        ),
        CheckConstraint(
            "approved_credits IS NULL OR approved_credits > 0",
            name="ck_cbt_ai_quota_requests_approved_positive",
        ),
        CheckConstraint(
            """
            (
                status = 'pending'
                AND reviewed_by_admin_id IS NULL
                AND approved_credits IS NULL
                AND allocation_id IS NULL
                AND reviewed_at IS NULL
                AND cancelled_at IS NULL
            )
            OR
            (
                status = 'approved'
                AND reviewed_by_admin_id IS NOT NULL
                AND approved_credits IS NOT NULL
                AND allocation_id IS NOT NULL
                AND reviewed_at IS NOT NULL
                AND cancelled_at IS NULL
            )
            OR
            (
                status = 'rejected'
                AND reviewed_by_admin_id IS NOT NULL
                AND approved_credits IS NULL
                AND allocation_id IS NULL
                AND reviewed_at IS NOT NULL
                AND cancelled_at IS NULL
            )
            OR
            (
                status = 'cancelled'
                AND approved_credits IS NULL
                AND allocation_id IS NULL
                AND reviewed_at IS NULL
                AND cancelled_at IS NOT NULL
            )
            """,
            name="ck_cbt_ai_quota_requests_status_consistency",
        ),
        Index(
            "ix_cbt_ai_quota_requests_requester_status",
            "requester_quota_account_id",
            "status",
        ),
        Index(
            "ix_cbt_ai_quota_requests_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_cbt_ai_quota_requests_pending",
            "tenant_id",
            "created_at",
            postgresql_where=(status == AIQuotaRequestStatus.PENDING),
        ),
    )


class AIQuotaPurchase(BaseModel):
    """
    Records a tenant purchase of AI credits.

    The purchase starts as pending after Paystack initialization.

    Once the Paystack webhook confirms successful payment, the purchased
    credits are added to AITenantCreditBalalce and the purchase is marked
    successful.

    'credited_at' is used to prevent the same payment from crediting the
    tenant more than once
    """

    __tablename__ = "cbt_ai_quota_purchases"

    initiated_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenant_admins.id", ondelete="RESTRICT"),
        nullable=False,
    )

    credits: Mapped[int] = mapped_column(Integer, nullable=False)

    amount_kobo: Mapped[int] = mapped_column(Integer, nullable=False)

    reference: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    status: Mapped[AIQuotaPurchaseStatus] = mapped_column(
        SQLEnum(
            AIQuotaPurchaseStatus,
            name="cbt_ai_quota_purchase_status",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=AIQuotaPurchaseStatus.PENDING,
        server_default=AIQuotaPurchaseStatus.PENDING.value,
    )

    credited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "credits > 0",
            name="ck_cbt_ai_quota_purchases_positive_credits",
        ),
        CheckConstraint(
            "amount_kobo > 0",
            name="ck_cbt_ai_quota_purchases_positive_amount",
        ),
        CheckConstraint(
            """
            (
                status = 'success'
                AND credited_at IS NOT NULL
            )
            OR
            (
                status <> 'success'
                AND credited_at IS NULL
            )
            """,
            name="ck_cbt_ai_quota_purchases_credit_status_consistency",
        ),
        Index(
            "ix_cbt_ai_quota_purchases_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_cbt_ai_quota_purchases_admin",
            "initiated_by_admin_id",
        ),
        Index(
            "ix_cbt_ai_quota_purchases_created",
            "tenant_id",
            "created_at",
        ),
    )


class AICreditLedgerEventType(str, PyEnum):
    """Actual credit movements recorded by the AI accounting system."""

    PURCHASE = "purchase"
    ALLOCATION_OUT = "allocation_out"
    ALLOCATION_IN = "allocation_in"
    CONSUMPTION = "consumption"
    ADJUSTMENT = "adjustment"


class AICreditLedger(BaseModel):
    """
    Append-only audit ledger for real AI credit movements.

    Reservations are intentionally excluded because they are temporary holds,
    not actual credit movements.

    Examples:
        Tenant purchases 1,000 credits:
            bucket = tenant_reserve
            event_type = purchase
            credit_delta = +1000

        Admin allocates 100 credits:
            tenant reserve:
                credit_delta = -100

            teacher top-up:
                credit_delta = +100

        Teacher consumes 6 weekly credits:
            bucket = weekly_free
            event_type = consumption
            credit_delta = -6
    """

    __tablename__ = "cbt_ai_credit_ledger"

    quota_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_ai_quota_accounts.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    bucket: Mapped[AICreditLedgerBucket] = mapped_column(
        SQLEnum(
            AICreditLedgerBucket,
            name="cbt_ai_credit_ledger_bucket",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )

    event_type: Mapped[AICreditLedgerEventType] = mapped_column(
        SQLEnum(
            AICreditLedgerEventType,
            name="cbt_ai_credit_ledger_event_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )

    credit_delta: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_ai_credit_reservations.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    allocation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_ai_credit_allocations.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_ai_quota_purchases.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "credit_delta <> 0",
            name="ck_cbt_ai_credit_ledger_nonzero_delta",
        ),
        CheckConstraint(
            """
            (
                bucket = 'tenant_reserve'
                AND quota_account_id IS NULL
            )
            OR
            (
                bucket IN ('weekly_free', 'top_up')
                AND quota_account_id IS NOT NULL
            )
            """,
            name="ck_cbt_ai_credit_ledger_bucket_owner",
        ),
        Index(
            "ix_cbt_ai_credit_ledger_tenant_created",
            "tenant_id",
            "created_at",
        ),
        Index(
            "ix_cbt_ai_credit_ledger_account_created",
            "quota_account_id",
            "created_at",
        ),
        Index(
            "ix_cbt_ai_credit_ledger_reservation",
            "reservation_id",
        ),
        Index(
            "ix_cbt_ai_credit_ledger_allocation",
            "allocation_id",
        ),
        Index(
            "ix_cbt_ai_credit_ledger_purchase",
            "purchase_id",
        ),
    )
