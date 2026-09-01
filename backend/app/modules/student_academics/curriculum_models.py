"""V2 curriculum and term-specialization models.

Curricula belong to academic levels. Departments are canonical tenant-wide
concepts, while AcademicLevelDepartment supplies the exact level specialization
identity used by offerings and class-term placements.
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
        UUID(as_uuid=True), ForeignKey("academic_levels.id", ondelete="RESTRICT"), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "academic_level_id", name="uq_curricula_tenant_level"),
    )


class CurriculumSubject(BaseModel):
    __tablename__ = "curriculum_subjects"
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curricula.id", ondelete="RESTRICT"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
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
        UUID(as_uuid=True), ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False
    )
    academic_level_department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_level_departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_admins.id", ondelete="SET NULL"), nullable=True
    )
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "class_id", "academic_term_id", name="uq_class_term_department_assignment"
        ),
        Index("ix_class_term_department_tenant_term", "tenant_id", "academic_term_id"),
        Index(
            "ix_class_term_department_tenant_level_department",
            "tenant_id",
            "academic_level_department_id",
        ),
    )


class CurriculumOffering(BaseModel):
    __tablename__ = "curriculum_offerings"
    curriculum_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_subjects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False
    )
    academic_level_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_level_departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "curriculum_subject_id",
            "academic_term_id",
            "academic_level_department_id",
            name="uq_curriculum_offering_scope",
        ),
        Index(
            "uq_curriculum_offering_general_scope",
            "tenant_id",
            "curriculum_subject_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text("academic_level_department_id IS NULL"),
        ),
        Index("ix_curriculum_offerings_tenant_term", "tenant_id", "academic_term_id"),
        Index(
            "ix_curriculum_offerings_tenant_level_department",
            "tenant_id",
            "academic_level_department_id",
        ),
    )
