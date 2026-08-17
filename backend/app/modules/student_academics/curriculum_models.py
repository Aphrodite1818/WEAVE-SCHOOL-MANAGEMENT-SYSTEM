"""V2 curriculum and term-specialization models.

These models are the new academic-structure source of truth. They deliberately
avoid class-level curriculum duplication and student-level department state.
"""

from __future__ import annotations

import uuid
from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel


class Curriculum(BaseModel):
    __tablename__ = "curricula"
    academic_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_levels.id", ondelete="CASCADE"), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "academic_level_id", name="uq_curricula_tenant_level"),
    )


class CurriculumSubject(BaseModel):
    __tablename__ = "curriculum_subjects"
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    is_elective: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "curriculum_id",
            "subject_id",
            name="uq_curriculum_subject_tenant_curriculum_subject",
        ),
        Index("ix_curriculum_subjects_tenant_curriculum", "tenant_id", "curriculum_id"),
    )


class ClassTermDepartmentAssignment(BaseModel):
    __tablename__ = "class_term_department_assignments"
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_admins.id", ondelete="SET NULL"), nullable=True
    )
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "class_id", "academic_term_id", name="uq_class_term_department_assignment"
        ),
        Index("ix_class_term_department_tenant_term", "tenant_id", "academic_term_id"),
    )


class CurriculumOffering(BaseModel):
    __tablename__ = "curriculum_offerings"
    curriculum_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_subjects.id", ondelete="CASCADE"), nullable=False
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True
    )
    __table_args__ = (
        # This constraint enforces one row per concrete department. PostgreSQL
        # treats NULL as distinct, so General offerings need the partial index below.
        UniqueConstraint(
            "tenant_id",
            "curriculum_subject_id",
            "academic_term_id",
            "department_id",
            name="uq_curriculum_offering_scope",
        ),
        Index(
            "uq_curriculum_offering_general_scope",
            "tenant_id",
            "curriculum_subject_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text("department_id IS NULL"),
        ),
        Index("ix_curriculum_offerings_tenant_term", "tenant_id", "academic_term_id"),
    )
