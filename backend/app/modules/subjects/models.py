"""Tenant-scoped subject catalog for each school."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel

if TYPE_CHECKING:
    from app.modules.teachers.models import TeacherMembership
    from app.modules.teachers.models import TeacherMembershipSubject


class Subject(BaseModel):
    """Represent a tenant-wide school subject catalogue entry."""

    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    normalized_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    teacher_links: Mapped[list["TeacherMembershipSubject"]] = relationship(
        "TeacherMembershipSubject",
        back_populates="subject",
        cascade="all, delete-orphan",
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    archived_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    @property
    def teachers(self) -> list["TeacherMembership"]:
        return [link.teacher_membership for link in self.teacher_links]

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_subject_tenant_name"),
        UniqueConstraint("tenant_id", "code", name="uq_subject_tenant_code"),
        UniqueConstraint("tenant_id", "normalized_name", name="uq_subject_tenant_normalized_name"),
        UniqueConstraint("tenant_id", "normalized_code", name="uq_subject_tenant_normalized_code"),
        CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_subjects_archived_requires_inactive",
        ),
        Index(
            "ix_subjects_tenant_archived",
            "tenant_id",
            "archived_at",
        ),
    )
