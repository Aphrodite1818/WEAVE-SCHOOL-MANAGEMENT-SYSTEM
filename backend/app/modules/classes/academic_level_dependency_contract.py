"""Canonical academic-level dependency accounting after the department-pool cutover."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.classes.models import AcademicLevelDepartment, ClassRoom
from app.modules.classes.repository import AcademicLevelRepository
from app.modules.student_academics.curriculum_models import Curriculum, CurriculumSubject
from app.modules.students.models import StudentEnrollment


async def count_setup_dependencies(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    level_id: uuid.UUID,
) -> dict[str, int]:
    """Count level dependencies against the canonical v2 academic graph."""

    def count_subquery(model, *conditions):
        return select(func.count()).select_from(model).where(*conditions).scalar_subquery()

    curriculum_ids = select(Curriculum.id).where(
        Curriculum.tenant_id == tenant_id,
        Curriculum.academic_level_id == level_id,
    )

    row = (
        await db.execute(
            select(
                count_subquery(
                    ClassRoom,
                    ClassRoom.tenant_id == tenant_id,
                    ClassRoom.academic_level_id == level_id,
                ).label("classes_total"),
                count_subquery(
                    ClassRoom,
                    ClassRoom.tenant_id == tenant_id,
                    ClassRoom.academic_level_id == level_id,
                    ClassRoom.is_active.is_(True),
                    ClassRoom.archived_at.is_(None),
                ).label("classes_active"),
                count_subquery(
                    AcademicLevelDepartment,
                    AcademicLevelDepartment.tenant_id == tenant_id,
                    AcademicLevelDepartment.academic_level_id == level_id,
                ).label("departments_total"),
                count_subquery(
                    AcademicLevelDepartment,
                    AcademicLevelDepartment.tenant_id == tenant_id,
                    AcademicLevelDepartment.academic_level_id == level_id,
                    AcademicLevelDepartment.is_active.is_(True),
                    AcademicLevelDepartment.archived_at.is_(None),
                ).label("departments_active"),
                count_subquery(
                    CurriculumSubject,
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.curriculum_id.in_(curriculum_ids),
                ).label("curriculum_subjects_total"),
                count_subquery(
                    CurriculumSubject,
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.curriculum_id.in_(curriculum_ids),
                    CurriculumSubject.is_active.is_(True),
                ).label("curriculum_subjects_active"),
                count_subquery(
                    StudentEnrollment,
                    StudentEnrollment.tenant_id == tenant_id,
                    StudentEnrollment.academic_level_id == level_id,
                ).label("enrollments_total"),
                count_subquery(
                    StudentEnrollment,
                    StudentEnrollment.tenant_id == tenant_id,
                    StudentEnrollment.academic_level_id == level_id,
                    StudentEnrollment.is_current.is_(True),
                ).label("enrollments_current"),
            )
        )
    ).one()
    return {
        "classes_total": int(row.classes_total),
        "classes_active": int(row.classes_active),
        "departments_total": int(row.departments_total),
        "departments_active": int(row.departments_active),
        "curriculum_subjects_total": int(row.curriculum_subjects_total),
        "curriculum_subjects_active": int(row.curriculum_subjects_active),
        "enrollments_total": int(row.enrollments_total),
        "enrollments_current": int(row.enrollments_current),
    }


# AcademicLevelService imports this class directly. Replace the obsolete
# level-owned Department query with the canonical mapping-aware implementation.
AcademicLevelRepository.count_setup_dependencies = staticmethod(count_setup_dependencies)
