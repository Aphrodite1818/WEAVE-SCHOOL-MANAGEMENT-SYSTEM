# ====================================== #
#              models.py                 #
# ====================================== #
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.utils.normalization import (
    normalize_class_arm,
    normalize_class_name,
    normalized_class_arm_key,
    normalized_class_name_key,
)
from app.shared.base_model import BaseModel

if TYPE_CHECKING:
    from app.modules.teachers.models import TeacherMembership


class ClassRoom(BaseModel):
    """Tenant-scoped academic class model."""

    __tablename__ = "classes"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    arm: Mapped[str | None] = mapped_column(String(20), nullable=True)
    normalized_arm: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    teacher_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    next_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    teacher_membership: Mapped["TeacherMembership | None"] = relationship(
        "TeacherMembership",
        foreign_keys=[teacher_membership_id],
    )
    next_class: Mapped["ClassRoom | None"] = relationship(
        "ClassRoom",
        foreign_keys=[next_class_id],
        remote_side="ClassRoom.id",
        back_populates="previous_classes",
    )
    previous_classes: Mapped[list["ClassRoom"]] = relationship(
        "ClassRoom",
        foreign_keys="ClassRoom.next_class_id",
        back_populates="next_class",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_name", "normalized_arm", name="uq_classes_tenant_normalized_name_arm"),
        CheckConstraint("next_class_id IS NULL OR next_class_id <> id", name="ck_classes_next_class_not_self"),
        CheckConstraint(
            "(is_terminal = true AND next_class_id IS NULL) OR is_terminal = false",
            name="ck_classes_terminal_has_no_next_class",
        ),
        Index("ix_classes_tenant_teacher_membership", "tenant_id", "teacher_membership_id"),
        Index("ix_classes_tenant_active", "tenant_id", "is_active"),
        Index("ix_classes_tenant_next_class", "tenant_id", "next_class_id"),
        Index("ix_classes_tenant_terminal_active", "tenant_id", "is_terminal", "is_active"),
    )


def _populate_classroom_normalized_fields(_: object, __: object, target: ClassRoom) -> None:
    normalized_name = normalized_class_name_key(target.name)
    if normalized_name is None:
        return
    target.name = normalize_class_name(target.name) or target.name
    target.arm = normalize_class_arm(target.arm)
    target.normalized_name = normalized_name
    target.normalized_arm = normalized_class_arm_key(target.arm)


event.listen(ClassRoom, "before_insert", _populate_classroom_normalized_fields)
event.listen(ClassRoom, "before_update", _populate_classroom_normalized_fields)
