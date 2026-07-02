"""Tenant-scoped subject catalog for each school."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel

if TYPE_CHECKING:
    from app.modules.teachers.models import Teacher, TeacherSubject


class Subject(BaseModel):
    """Represent a tenant-wide school subject catalogue entry."""

    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    normalized_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    teacher_links: Mapped[list["TeacherSubject"]] = relationship(
        "TeacherSubject",
        back_populates="subject",
        cascade="all, delete-orphan",
        overlaps="teachers,subjects",
    )

    teachers: Mapped[list["Teacher"]] = relationship(
        secondary="public.teacher_subjects",
        back_populates="subjects",
        overlaps="teacher_links,subject_links,teacher,subject",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_subject_tenant_name"),
        UniqueConstraint("tenant_id", "code", name="uq_subject_tenant_code"),
        UniqueConstraint("tenant_id", "normalized_name", name="uq_subject_tenant_normalized_name"),
        UniqueConstraint("tenant_id", "normalized_code", name="uq_subject_tenant_normalized_code"),
    )
