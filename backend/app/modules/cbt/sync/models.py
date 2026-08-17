"""Durable PostgreSQL-backed CBT synchronization models."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, Enum as SQLEnum, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.cbt.sync.enums import CBTSyncEntityType, CBTSyncOperation
from app.shared.base_model import Base, BaseModel, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin


cbt_sync_operation_enum = SQLEnum(
    CBTSyncOperation,
    name="cbt_sync_operation",
    schema=PUBLIC_SCHEMA,
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)
cbt_sync_entity_enum = SQLEnum(
    CBTSyncEntityType,
    name="cbt_sync_entity_type",
    schema=PUBLIC_SCHEMA,
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)


class CBTSyncTenantState(TimestampMixin, Base):
    __tablename__ = "cbt_sync_tenant_states"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenants.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    last_cursor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )


class CBTSyncChange(BaseModel):
    __tablename__ = "cbt_sync_changes"

    cursor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[CBTSyncEntityType] = mapped_column(cbt_sync_entity_enum, nullable=False)
    operation: Mapped[CBTSyncOperation] = mapped_column(cbt_sync_operation_enum, nullable=False)
    schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        server_default=text("2"),
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "cursor", name="uq_cbt_sync_changes_tenant_cursor"),
        Index("ix_cbt_sync_changes_tenant_entity", "tenant_id", "entity_type", "entity_id"),
        Index("ix_cbt_sync_changes_created_at", "created_at"),
    )
