# ========================== #
#   bulk_imports_models.py   #
# ========================== #

"""Table definitions for tracking tenant bulk import jobs."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


if TYPE_CHECKING:
    from app.modules.tenant_admins.models import TenantAdmin


class ImportResourceType(str, PyEnum):
    """Supported resource types for tenant bulk imports."""

    STUDENTS = "students"


class ImportFileType(str, PyEnum):
    """Supported upload file types."""

    CSV = "csv"
    XLSX = "xlsx"


class ImportJobStatus(str, PyEnum):
    """Lifecycle state of an import job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImportNotificationChannel(str, PyEnum):
    """Channel used to notify admins about import results."""

    IN_APP = "in_app"
    EMAIL = "email"


class ImportNotificationStatus(str, PyEnum):
    """Delivery state for an import notification."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class ImportJob(BaseModel):
    """Tracks a tenant bulk import job from upload to completion."""

    __tablename__ = "import_jobs"

    resource_type: Mapped[ImportResourceType] = mapped_column(
        SQLEnum(
            ImportResourceType,
            name="import_resource_type",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    file_type: Mapped[ImportFileType] = mapped_column(
        SQLEnum(
            ImportFileType,
            name="import_file_type",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    status: Mapped[ImportJobStatus] = mapped_column(
        SQLEnum(
            ImportJobStatus,
            name="import_job_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ImportJobStatus.PENDING,
        server_default=ImportJobStatus.PENDING.value,
    )

    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenant_admins.id"),
        nullable=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    stored_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    source_file_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    result_file_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    total_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    processed_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    successful_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    failed_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    skipped_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )

    created_by_admin: Mapped["TenantAdmin | None"] = relationship(
        "TenantAdmin",
        foreign_keys=[created_by_admin_id],
    )

    row_errors: Mapped[list["ImportRowError"]] = relationship(
        "ImportRowError",
        back_populates="import_job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    staged_rows: Mapped[list["ImportStagedRow"]] = relationship(
        "ImportStagedRow",
        back_populates="import_job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    notifications: Mapped[list["ImportNotification"]] = relationship(
        "ImportNotification",
        back_populates="import_job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_import_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_import_jobs_tenant_resource_type", "tenant_id", "resource_type"),
        Index("ix_import_jobs_tenant_created_by", "tenant_id", "created_by_admin_id"),
        Index("ix_import_jobs_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_import_jobs_status_created_at", "status", "created_at"),
    )


class ImportRowError(BaseModel):
    """Stores row-level validation or processing errors for an import job."""

    __tablename__ = "import_row_errors"

    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    field_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    error_code: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    raw_row: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    normalized_row: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    import_job: Mapped["ImportJob"] = relationship(
        "ImportJob",
        back_populates="row_errors",
    )

    __table_args__ = (
        Index("ix_import_row_errors_tenant_job", "tenant_id", "import_job_id"),
        Index(
            "ix_import_row_errors_tenant_job_row",
            "tenant_id",
            "import_job_id",
            "row_number",
        ),
        Index("ix_import_row_errors_tenant_error_code", "tenant_id", "error_code"),
    )


class ImportStagedRow(BaseModel):
    """Stores valid dry-run rows that can later be confirmed for real creation."""

    __tablename__ = "import_staged_rows"

    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    raw_row: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    normalized_row: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    import_job: Mapped["ImportJob"] = relationship(
        "ImportJob",
        back_populates="staged_rows",
    )

    __table_args__ = (
        UniqueConstraint("import_job_id", "row_number", name="uq_import_staged_rows_job_row"),
        Index("ix_import_staged_rows_tenant_job", "tenant_id", "import_job_id"),
        Index("ix_import_staged_rows_job_row", "import_job_id", "row_number"),
    )


class ImportNotification(BaseModel):
    """Tracks notifications generated from import job completion or failure."""

    __tablename__ = "import_notifications"

    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    recipient_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenant_admins.id"),
        nullable=True,
    )

    channel: Mapped[ImportNotificationChannel] = mapped_column(
        SQLEnum(
            ImportNotificationChannel,
            name="import_notification_channel",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ImportNotificationChannel.IN_APP,
        server_default=ImportNotificationChannel.IN_APP.value,
    )

    status: Mapped[ImportNotificationStatus] = mapped_column(
        SQLEnum(
            ImportNotificationStatus,
            name="import_notification_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ImportNotificationStatus.PENDING,
        server_default=ImportNotificationStatus.PENDING.value,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    import_job: Mapped["ImportJob"] = relationship(
        "ImportJob",
        back_populates="notifications",
    )

    recipient_admin: Mapped["TenantAdmin | None"] = relationship(
        "TenantAdmin",
        foreign_keys=[recipient_admin_id],
    )

    __table_args__ = (
        Index("ix_import_notifications_tenant_job", "tenant_id", "import_job_id"),
        Index("ix_import_notifications_tenant_recipient", "tenant_id", "recipient_admin_id"),
        Index("ix_import_notifications_tenant_status", "tenant_id", "status"),
        Index("ix_import_notifications_tenant_read", "tenant_id", "is_read"),
    )
