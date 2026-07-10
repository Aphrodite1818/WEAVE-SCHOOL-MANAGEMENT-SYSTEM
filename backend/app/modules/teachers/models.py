"""Teacher domain models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA

if TYPE_CHECKING:
    from app.modules.subjects.models import Subject


class TeacherAccountStatus(str, PyEnum):
    """Teacher account lifecycle status."""

    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class TeacherStatus(str, PyEnum):
    """Teacher employment/profile status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class Teacher(BaseModel):
    """Teacher actor account and academic profile."""

    __tablename__ = "teachers"

    email: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    first_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    last_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    staff_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    qualification: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    specialization: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    passport_photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    account_status: Mapped[TeacherAccountStatus] = mapped_column(
        SQLEnum(
            TeacherAccountStatus,
            name="teacher_account_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=TeacherAccountStatus.PENDING,
        server_default=TeacherAccountStatus.PENDING.value,
    )

    status: Mapped[TeacherStatus] = mapped_column(
        SQLEnum(
            TeacherStatus,
            name="teacher_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=TeacherStatus.ACTIVE,
        server_default=TeacherStatus.ACTIVE.value,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    subject_links: Mapped[list["TeacherSubject"]] = relationship(
        "TeacherSubject",
        back_populates="teacher",
        cascade="all, delete-orphan",
        overlaps="subjects,teachers",
    )

    subjects: Mapped[list["Subject"]] = relationship(
        secondary="public.teacher_subjects",
        back_populates="teachers",
        overlaps="subject_links,teacher_links,teacher,subject",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "staff_id",
            name="uq_teachers_tenant_staff_id",
        ),
        Index(
            "ix_teachers_tenant_email",
            "tenant_id",
            "email",
        ),
        Index(
            "ix_teachers_tenant_status",
            "tenant_id",
            "status",
        ),
    )

    @property
    def profile_completed(self) -> bool:
        """Return whether the teacher completed the required self-service fields."""

        return bool(
            self.first_name
            and self.first_name.strip()
            and self.last_name
            and self.last_name.strip()
        )


class TeacherSubject(BaseModel):
    """Link table between teachers and subjects."""

    __tablename__ = "teacher_subjects"

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teachers.id", ondelete="CASCADE"),
        nullable=False,
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )

    teacher: Mapped["Teacher"] = relationship(
        "Teacher",
        back_populates="subject_links",
        overlaps="subjects,teachers",
    )

    subject: Mapped["Subject"] = relationship(
        "Subject",
        back_populates="teacher_links",
        overlaps="subjects,teachers",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "teacher_id",
            "subject_id",
            name="uq_teacher_subjects_tenant_teacher_subject",
        ),
        Index("ix_teacher_subjects_tenant_teacher", "tenant_id", "teacher_id"),
        Index("ix_teacher_subjects_tenant_subject", "tenant_id", "subject_id"),
    )
