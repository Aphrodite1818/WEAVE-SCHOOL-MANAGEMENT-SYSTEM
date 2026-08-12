# ====================================== #
#              models.py                 #
# ====================================== #
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.teachers.models import TeacherMembership

from datetime import datetime
from enum import Enum as PyEnum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.utils.normalization import (
    normalize_class_arm,
    normalize_class_name,
    normalized_class_arm_key,
    normalized_class_name_key,
)
from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


def enum_values(enum_cls):
    return [item.value for item in enum_cls]


class AcademicLevelProgressionMode(str, PyEnum):
    DIRECT = "direct"
    STUDENT_SELECTION = "student_selection"
    TERMINAL = "terminal"


class ProgressionSelectionTargetType(str, PyEnum):
    LEVEL = "level"
    CLASSROOM = "classroom"


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
    progression_mode: Mapped[AcademicLevelProgressionMode] = mapped_column(
        SQLEnum(
            AcademicLevelProgressionMode,
            name="academic_level_progression_mode",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=AcademicLevelProgressionMode.DIRECT,
        server_default=AcademicLevelProgressionMode.DIRECT.value,
    )
    selection_target_type: Mapped[ProgressionSelectionTargetType | None] = mapped_column(
        SQLEnum(
            ProgressionSelectionTargetType,
            name="progression_selection_target_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=True,
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
    progression_selection_options: Mapped[list["ProgressionSelectionOption"]] = relationship(
        "ProgressionSelectionOption",
        foreign_keys="ProgressionSelectionOption.source_level_id",
        back_populates="source_level",
        cascade="all, delete-orphan",
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
            "(progression_mode = 'direct' AND selection_target_type IS NULL) "
            "OR (progression_mode = 'student_selection' AND next_level_id IS NULL AND selection_target_type IS NOT NULL) "
            "OR (progression_mode = 'terminal' AND next_level_id IS NULL AND selection_target_type IS NULL)",
            name="ck_academic_levels_progression_configuration",
        ),
        CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_academic_levels_archived_requires_inactive",
        ),
        Index("ix_academic_levels_tenant_active", "tenant_id", "is_active"),
        Index("ix_academic_levels_tenant_next", "tenant_id", "next_level_id"),
        Index("ix_academic_levels_tenant_archived", "tenant_id", "archived_at"),
    )


class ProgressionSelectionOption(BaseModel):
    """Explicit tenant-owned destination offered for student selection."""

    __tablename__ = "progression_selection_options"

    source_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_levels.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_level_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_levels.id", ondelete="RESTRICT"),
        nullable=True,
    )
    target_classroom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=True,
    )

    source_level: Mapped[AcademicLevel] = relationship(
        "AcademicLevel",
        foreign_keys=[source_level_id],
        back_populates="progression_selection_options",
    )
    target_level: Mapped[AcademicLevel | None] = relationship(
        "AcademicLevel", foreign_keys=[target_level_id]
    )
    target_classroom: Mapped["ClassRoom | None"] = relationship(
        "ClassRoom", foreign_keys=[target_classroom_id]
    )

    __table_args__ = (
        CheckConstraint(
            "(target_level_id IS NOT NULL) <> (target_classroom_id IS NOT NULL)",
            name="ck_progression_selection_option_exactly_one_target",
        ),
        CheckConstraint(
            "target_level_id IS NULL OR target_level_id <> source_level_id",
            name="ck_progression_selection_option_level_not_self",
        ),
        Index(
            "uq_progression_selection_option_level",
            "tenant_id",
            "source_level_id",
            "target_level_id",
            unique=True,
            postgresql_where=text("target_level_id IS NOT NULL"),
        ),
        Index(
            "uq_progression_selection_option_classroom",
            "tenant_id",
            "source_level_id",
            "target_classroom_id",
            unique=True,
            postgresql_where=text("target_classroom_id IS NOT NULL"),
        ),
        Index(
            "ix_progression_selection_options_tenant_source",
            "tenant_id",
            "source_level_id",
        ),
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
