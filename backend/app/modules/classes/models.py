# ====================================== #
#              models.py                 #
# ====================================== #
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.teachers.models import TeacherMembership

from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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


class AcademicLevel(BaseModel):
    """Tenant-scoped curriculum level shared by concrete class arms."""

    __tablename__ = "academic_levels"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    next_level_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_levels.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_terminal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    next_level: Mapped["AcademicLevel | None"] = relationship(
        "AcademicLevel",
        foreign_keys=[next_level_id],
        remote_side="AcademicLevel.id",
        back_populates="previous_levels",
    )
    previous_levels: Mapped[list["AcademicLevel"]] = relationship(
        "AcademicLevel",
        foreign_keys="AcademicLevel.next_level_id",
        back_populates="next_level",
    )
    classrooms: Mapped[list["ClassRoom"]] = relationship(
        "ClassRoom", back_populates="academic_level"
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "normalized_name", name="uq_academic_levels_tenant_normalized_name"
        ),
        CheckConstraint(
            "next_level_id IS NULL OR next_level_id <> id",
            name="ck_academic_levels_next_not_self",
        ),
        CheckConstraint(
            "(is_terminal = true AND next_level_id IS NULL) OR is_terminal = false",
            name="ck_academic_levels_terminal_has_no_next",
        ),
        CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_academic_levels_archived_requires_inactive",
        ),
        Index("ix_academic_levels_tenant_active", "tenant_id", "is_active"),
        Index("ix_academic_levels_tenant_next", "tenant_id", "next_level_id"),
        Index("ix_academic_levels_tenant_archived", "tenant_id", "archived_at"),
    )


def _populate_academic_level_normalized_fields(
    _: object, __: object, target: AcademicLevel
) -> None:
    normalized_name = normalized_class_name_key(target.name)
    if normalized_name is None:
        return
    target.name = normalize_class_name(target.name) or target.name
    target.normalized_name = normalized_name


event.listen(AcademicLevel, "before_insert", _populate_academic_level_normalized_fields)
event.listen(AcademicLevel, "before_update", _populate_academic_level_normalized_fields)


class ClassRoom(BaseModel):
    """Tenant-scoped concrete class arm belonging to an academic level."""

    __tablename__ = "classes"

    academic_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_levels.id", ondelete="RESTRICT"),
        nullable=False,
    )
    arm: Mapped[str] = mapped_column(String(20), nullable=False)
    normalized_arm: Mapped[str] = mapped_column(
        String(40), nullable=False, default="", server_default=""
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
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

    teacher_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    academic_level: Mapped[AcademicLevel] = relationship(
        "AcademicLevel", back_populates="classrooms", foreign_keys=[academic_level_id]
    )
    teacher_membership: Mapped[TeacherMembership | None] = relationship(
        "TeacherMembership",
        foreign_keys=[teacher_membership_id],
    )

    @property
    def academic_level_name(self) -> str:
        return self.academic_level.name

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "academic_level_id",
            "normalized_arm",
            name="uq_classes_tenant_level_arm",
        ),
        CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_classes_archived_requires_inactive",
        ),
        Index("ix_classes_tenant_teacher_membership", "tenant_id", "teacher_membership_id"),
        Index("ix_classes_tenant_active", "tenant_id", "is_active"),
        Index("ix_classes_tenant_level", "tenant_id", "academic_level_id"),
        Index(
            "ix_classes_tenant_archived",
            "tenant_id",
            "archived_at",
        ),
    )


def _populate_classroom_normalized_fields(_: object, __: object, target: ClassRoom) -> None:
    target.arm = normalize_class_arm(target.arm)
    target.normalized_arm = normalized_class_arm_key(target.arm)


event.listen(ClassRoom, "before_insert", _populate_classroom_normalized_fields)
event.listen(ClassRoom, "before_update", _populate_classroom_normalized_fields)
