"""Models for CBT -> Weave result-ingestion auditing."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.cbt.enums import (
    CBTResultIngestionOutcome,
    CBTResultIngestionStatus,
)
from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


class CBTResultIngestionBatch(BaseModel):
    """
    Immutable audit record for one result batch received from a paired CBT server.

    Academic identifiers supplied by CBT are intentionally stored as raw UUIDs
    so stale or invalid client references can still be preserved for auditing.
    """

    __tablename__ = "cbt_result_ingestion_batches"

    # ------------------------------------------------------------------
    # Authenticated machine identity
    # ------------------------------------------------------------------

    cbt_server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_servers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    credential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_server_credentials.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Client / idempotency identity
    # ------------------------------------------------------------------

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    source_exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Academic context asserted by CBT
    # ------------------------------------------------------------------

    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    academic_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    curriculum_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    assessment_component_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    exam_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Processing state
    # ------------------------------------------------------------------

    status: Mapped[CBTResultIngestionStatus] = mapped_column(
        SQLEnum(
            CBTResultIngestionStatus,
            name="cbt_result_ingestion_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=CBTResultIngestionStatus.PROCESSING,
        server_default=CBTResultIngestionStatus.PROCESSING.value,
    )

    received_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    applied_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    unchanged_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    rejected_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    batch_error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    batch_error_detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "cbt_server_id",
            "batch_id",
            name="uq_cbt_result_ingestion_tenant_server_batch",
        ),
        Index(
            "ix_cbt_result_ingestion_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_cbt_result_ingestion_tenant_server",
            "tenant_id",
            "cbt_server_id",
        ),
        Index(
            "ix_cbt_result_ingestion_tenant_source_exam",
            "tenant_id",
            "source_exam_id",
        ),
        Index(
            "ix_cbt_result_ingestion_tenant_component",
            "tenant_id",
            "assessment_component_id",
        ),
        Index(
            "ix_cbt_result_ingestion_tenant_period",
            "tenant_id",
            "academic_session_id",
            "academic_term_id",
        ),
        Index(
            "ix_cbt_result_ingestion_tenant_level_subject",
            "tenant_id",
            "academic_level_id",
            "curriculum_subject_id",
        ),
        CheckConstraint(
            """
            received_count >= 0
            AND applied_count >= 0
            AND unchanged_count >= 0
            AND rejected_count >= 0
            """,
            name="ck_cbt_result_ingestion_nonnegative_counts",
        ),
        CheckConstraint(
            """
            applied_count + unchanged_count + rejected_count
            <= received_count
            """,
            name="ck_cbt_result_ingestion_processed_not_over_received",
        ),
        CheckConstraint(
            """
            status = 'processing'
            OR processed_at IS NOT NULL
            """,
            name="ck_cbt_result_ingestion_finished_has_processed_at",
        ),
        CheckConstraint(
            """
            status NOT IN (
                'completed',
                'completed_with_rejections',
                'rejected'
            )
            OR applied_count + unchanged_count + rejected_count = received_count
            """,
            name="ck_cbt_result_ingestion_finished_counts_match",
        ),
    )


class CBTResultIngestionItem(BaseModel):
    """
    Immutable audit evidence for one student score submitted inside a CBT batch.

    submitted_student_id is intentionally not a foreign key so attempts using
    invalid, stale, or cross-tenant student identifiers can still be recorded.
    """

    __tablename__ = "cbt_result_ingestion_items"

    ingestion_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_result_ingestion_batches.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # Exact student identity supplied by CBT.
    submitted_student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    # Canonical ownership resolved by Weave.
    resolved_teacher_assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    incoming_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    previous_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    resulting_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    student_subject_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    outcome: Mapped[CBTResultIngestionOutcome] = mapped_column(
        SQLEnum(
            CBTResultIngestionOutcome,
            name="cbt_result_ingestion_outcome",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "ingestion_batch_id",
            "submitted_student_id",
            name="uq_cbt_result_ingestion_item_batch_student",
        ),
        Index(
            "ix_cbt_result_ingestion_item_tenant_batch",
            "tenant_id",
            "ingestion_batch_id",
        ),
        Index(
            "ix_cbt_result_ingestion_item_tenant_student",
            "tenant_id",
            "submitted_student_id",
        ),
        Index(
            "ix_cbt_result_ingestion_item_tenant_outcome",
            "tenant_id",
            "outcome",
        ),
        Index(
            "ix_cbt_result_ingestion_item_result",
            "tenant_id",
            "student_subject_result_id",
        ),
        Index(
            "ix_cbt_result_ingestion_item_teacher_assignment",
            "tenant_id",
            "resolved_teacher_assignment_id",
        ),
        CheckConstraint(
            "incoming_score >= 0",
            name="ck_cbt_result_ingestion_item_incoming_score_nonnegative",
        ),
        CheckConstraint(
            "previous_score IS NULL OR previous_score >= 0",
            name="ck_cbt_result_ingestion_item_previous_score_nonnegative",
        ),
        CheckConstraint(
            "resulting_score IS NULL OR resulting_score >= 0",
            name="ck_cbt_result_ingestion_item_resulting_score_nonnegative",
        ),
        CheckConstraint(
            """
            outcome <> 'rejected'
            OR error_code IS NOT NULL
            """,
            name="ck_cbt_result_ingestion_item_rejection_has_error",
        ),
        CheckConstraint(
            """
            outcome = 'rejected'
            OR resulting_score IS NOT NULL
            """,
            name="ck_cbt_result_ingestion_item_success_has_resulting_score",
        ),
    )
