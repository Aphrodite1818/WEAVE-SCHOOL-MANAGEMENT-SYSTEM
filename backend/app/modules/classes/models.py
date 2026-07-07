# ====================================== #
#              models.py                 #
# ====================================== #

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel

if TYPE_CHECKING:
    from app.modules.teachers.models import Teacher


class ClassRoom(BaseModel):
    """Tenant-scoped academic class model."""

    __tablename__ = "classes"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    arm: Mapped[str | None] = mapped_column(String(20), nullable=True)
    normalized_arm: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teachers.id", ondelete="SET NULL"),
        nullable=True,
    )

    teacher: Mapped["Teacher | None"] = relationship("Teacher")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "normalized_name",
            "normalized_arm",
            name="uq_classes_tenant_normalized_name_arm",
        ),
        Index("ix_classes_tenant_teacher", "tenant_id", "teacher_id"),
        Index("ix_classes_tenant_active", "tenant_id", "is_active"),
        Index("ix_classes_tenant_normalized_lookup", "tenant_id", "normalized_name", "normalized_arm"),
    )
