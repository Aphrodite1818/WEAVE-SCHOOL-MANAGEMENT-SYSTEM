"""Models for user acceptance of Weave legal and compliance terms."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base
from app.shared.mixins import TimestampMixin, UUIDMixin


class LegalComplianceAcceptance(UUIDMixin, TimestampMixin, Base):
    """Records acceptance of a specific Weave legal policy version by one actor."""

    __tablename__ = "legal_compliance_acceptances"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "actor_type",
            "actor_id",
            "policy_version",
            name="uq_legal_acceptance_actor_policy",
        ),
        Index(
            "ix_legal_acceptances_actor_latest",
            "actor_type",
            "actor_id",
            "accepted_at",
        ),
    )
