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
    normalize_class_name,
    normalized_class_name_key,
)
from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


def enum_values(enum_cls):
    return [item.value for item in enum_cls]


class AcademicCategory(str, PyEnum):
    KINDERGARTEN = "KINDERGARTEN"
    PRIMARY = "PRIMARY"
    JUNIOR_SECONDARY = "JUNIOR_SECONDARY"
    SENIOR_SECONDARY = "SENIOR_SECONDARY"


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
    category: Mapped[AcademicCategory] = mapped_column(
        SQLEnum(
            AcademicCategory,
            name="academic_category",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(nullable=False)
    specialization_required_from_term_position: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    classrooms: Mapped[list["ClassRoom"]] = relationship(
        "ClassRoom", back_populates="academic_level"
    )
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "normalized_name", name="uq_academic_levels_tenant_normalized_name"
        ),
        UniqueConstraint(
            "tenant_id",
            "category",
            "position",
            name="uq_academic_levels_tenant_category_position",
        ),
        CheckConstraint("position > 0", name="ck_academic_levels_position_positive"),
        CheckConstraint(
            "specialization_required_from_term_position IS NULL OR "
            "specialization_required_from_term_position > 0",
            name="ck_academic_levels_specialization_term_positive",
        ),
        CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_academic_levels_archived_requires_inactive",
        ),
        Index("ix_academic_levels_tenant_active", "tenant_id", "is_active"),
        Index(
            "ix_academic_levels_tenant_category_position",
            "tenant_id",
            "category",
            "position",
        ),
        Index("ix_academic_levels_tenant_archived", "tenant_id", "archived_at"),
    )


class Department(BaseModel):
    """Tenant-defined specialization independent of class placement."""

    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_name", name="uq_departments_tenant_name"),
        CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_departments_archived_requires_inactive",
        ),
        Index("ix_departments_tenant_active", "tenant_id", "is_active"),
    )


class ArmLabel(BaseModel):
    """Tenant-wide reusable class arm label."""

    __tablename__ = "arm_labels"

    label: Mapped[str] = mapped_column(String(20), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(40), nullable=False)
    position: Mapped[int | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_label", name="uq_arm_labels_tenant_label"),
        CheckConstraint("position IS NULL OR position > 0", name="ck_arm_labels_position_positive"),
        CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_arm_labels_archived_requires_inactive",
        ),
        Index("ix_arm_labels_tenant_active", "tenant_id", "is_active"),
        Index("ix_arm_labels_tenant_position", "tenant_id", "position"),
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
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    arm_label_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("arm_labels.id", ondelete="RESTRICT"),
        nullable=True,
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
    department: Mapped[Department | None] = relationship(
        "Department",
        foreign_keys=[department_id],
    )
    arm_label_ref: Mapped[ArmLabel | None] = relationship(
        "ArmLabel",
        foreign_keys=[arm_label_id],
    )
    teacher_membership: Mapped[TeacherMembership | None] = relationship(
        "TeacherMembership",
        foreign_keys=[teacher_membership_id],
    )

    @property
    def academic_level_name(self) -> str:
        return self.academic_level.name

    @property
    def department_name(self) -> str | None:
        return self.department.name if self.department is not None else None

    @property
    def arm_label(self) -> str | None:
        return self.arm_label_ref.label if self.arm_label_ref is not None else None

    @property
    def arm(self) -> str | None:
        return self.arm_label

    @property
    def display_name(self) -> str:
        return " ".join(
            part
            for part in (
                self.academic_level_name,
                self.department_name,
                self.arm_label,
            )
            if part
        )

    __table_args__ = (
        Index(
            "uq_classes_tenant_level_department_arm",
            "tenant_id",
            "academic_level_id",
            text("COALESCE(department_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            text("COALESCE(arm_label_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            unique=True,
        ),
        CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_classes_archived_requires_inactive",
        ),
        Index("ix_classes_tenant_teacher_membership", "tenant_id", "teacher_membership_id"),
        Index("ix_classes_tenant_active", "tenant_id", "is_active"),
        Index("ix_classes_tenant_level", "tenant_id", "academic_level_id"),
        Index("ix_classes_tenant_department", "tenant_id", "department_id"),
        Index("ix_classes_tenant_arm_label", "tenant_id", "arm_label_id"),
        Index(
            "ix_classes_tenant_archived",
            "tenant_id",
            "archived_at",
        ),
    )
