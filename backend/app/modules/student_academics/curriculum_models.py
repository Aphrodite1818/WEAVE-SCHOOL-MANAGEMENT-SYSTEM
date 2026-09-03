"""Level-owned curriculum and term-specific class specialization models.

Curriculum membership is persistent. Department applicability is also persistent
and is expressed through CurriculumSubjectDepartment. Academic terms do not own
subject applicability; they only determine when specialization filtering is active
and which specialization a class uses for that exact term.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel


class Curriculum(BaseModel):
    __tablename__ = "curricula"

    academic_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_levels.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "academic_level_id",
            name="uq_curricula_tenant_level",
        ),
    )


class CurriculumSubject(BaseModel):
    __tablename__ = "curriculum_subjects"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_elective: Mapped[bool] = mapped_column(
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

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "curriculum_id",
            "subject_id",
            name="uq_curriculum_subject_tenant_curriculum_subject",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_curriculum_subjects_tenant_id"),
        Index(
            "ix_curriculum_subjects_tenant_curriculum",
            "tenant_id",
            "curriculum_id",
        ),
    )


class CurriculumSubjectDepartment(BaseModel):
    """Persistent department applicability for one level curriculum subject.

    A curriculum subject with no rows in this table is GENERAL and therefore
    applies to every specialization. One or more rows make it department-scoped.
    The referenced AcademicLevelDepartment preserves exact level identity.
    """

    __tablename__ = "curriculum_subject_departments"

    curriculum_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    academic_level_department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "curriculum_subject_id"],
            ["curriculum_subjects.tenant_id", "curriculum_subjects.id"],
            name="fk_curriculum_subject_department_tenant_subject",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "academic_level_department_id"],
            ["academic_level_departments.tenant_id", "academic_level_departments.id"],
            name="fk_curriculum_subject_department_tenant_level_department",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "curriculum_subject_id",
            "academic_level_department_id",
            name="uq_curriculum_subject_department_scope",
        ),
        Index(
            "ix_curriculum_subject_departments_tenant_subject",
            "tenant_id",
            "curriculum_subject_id",
        ),
        Index(
            "ix_curriculum_subject_departments_tenant_level_department",
            "tenant_id",
            "academic_level_department_id",
        ),
    )


class ClassTermDepartmentAssignment(BaseModel):
    """The exact specialization of one class in one academic term."""

    __tablename__ = "class_term_department_assignments"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_terms.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_level_department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_level_departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "class_id",
            "academic_term_id",
            name="uq_class_term_department_assignment",
        ),
        Index(
            "ix_class_term_department_tenant_term",
            "tenant_id",
            "academic_term_id",
        ),
        Index(
            "ix_class_term_department_tenant_level_department",
            "tenant_id",
            "academic_level_department_id",
        ),
    )
