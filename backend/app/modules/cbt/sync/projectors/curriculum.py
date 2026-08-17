"""Stable CBT projections for subjects, curricula, and term offerings."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cbt.academics.schemas import (
    CBTCurriculumOfferingSnapshot,
    CBTCurriculumSnapshot,
    CBTCurriculumSubjectSnapshot,
    CBTSubjectSnapshot,
)
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumOffering,
    CurriculumSubject,
)
from app.modules.students.models import AcademicStatus, Student, StudentEnrollment
from app.modules.subjects.models import Subject


def _visible(row: Any) -> bool:
    return bool(
        row is not None
        and getattr(row, "is_active", True)
        and getattr(row, "archived_at", None) is None
    )


def project_subject(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(Subject).where(Subject.tenant_id == tenant_id, Subject.id == entity_id)
    ).scalar_one_or_none()
    if not _visible(row):
        return None
    return CBTSubjectSnapshot(
        id=row.id,
        name=row.name,
        code=row.code,
        is_active=row.is_active,
    ).model_dump(mode="json")


def project_curriculum(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(Curriculum).where(
            Curriculum.tenant_id == tenant_id,
            Curriculum.id == entity_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return CBTCurriculumSnapshot(
        id=row.id,
        academic_level_id=row.academic_level_id,
    ).model_dump(mode="json")


def project_curriculum_subject(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(CurriculumSubject).where(
            CurriculumSubject.tenant_id == tenant_id,
            CurriculumSubject.id == entity_id,
        )
    ).scalar_one_or_none()
    if not _visible(row):
        return None
    return CBTCurriculumSubjectSnapshot(
        id=row.id,
        curriculum_id=row.curriculum_id,
        subject_id=row.subject_id,
        is_elective=row.is_elective,
        is_active=row.is_active,
    ).model_dump(mode="json")


def _eligible_enrollment_ids(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    academic_level_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    department_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    enrollment_rows = list(
        session.execute(
            select(StudentEnrollment.id, StudentEnrollment.class_id)
            .join(Student, Student.id == StudentEnrollment.student_id)
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.academic_level_id == academic_level_id,
                StudentEnrollment.is_current.is_(True),
                Student.status == AcademicStatus.ACTIVE,
                Student.is_archived.is_(False),
            )
        ).all()
    )
    if department_id is None:
        return [row.id for row in enrollment_rows]

    class_ids = [row.class_id for row in enrollment_rows if row.class_id is not None]
    if not class_ids:
        return []
    specialized_classes = set(
        session.execute(
            select(ClassTermDepartmentAssignment.class_id).where(
                ClassTermDepartmentAssignment.tenant_id == tenant_id,
                ClassTermDepartmentAssignment.academic_term_id == academic_term_id,
                ClassTermDepartmentAssignment.department_id == department_id,
                ClassTermDepartmentAssignment.class_id.in_(class_ids),
            )
        ).scalars()
    )
    return [
        row.id
        for row in enrollment_rows
        if row.class_id is not None and row.class_id in specialized_classes
    ]


def project_subject_offering(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    joined = session.execute(
        select(CurriculumOffering, CurriculumSubject, Curriculum)
        .join(
            CurriculumSubject,
            CurriculumSubject.id == CurriculumOffering.curriculum_subject_id,
        )
        .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
        .where(
            CurriculumOffering.tenant_id == tenant_id,
            CurriculumOffering.id == entity_id,
        )
    ).first()
    if joined is None:
        return None
    offering, curriculum_subject, curriculum = joined
    if not _visible(curriculum_subject):
        return None
    eligible = _eligible_enrollment_ids(
        session,
        tenant_id=tenant_id,
        academic_level_id=curriculum.academic_level_id,
        academic_term_id=offering.academic_term_id,
        department_id=offering.department_id,
    )
    return CBTCurriculumOfferingSnapshot(
        id=offering.id,
        curriculum_subject_id=offering.curriculum_subject_id,
        academic_term_id=offering.academic_term_id,
        department_id=offering.department_id,
        eligible_enrollment_ids=eligible,
    ).model_dump(mode="json")


def offering_ids_for_level_term(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    academic_level_id: uuid.UUID,
    academic_term_id: uuid.UUID,
) -> list[uuid.UUID]:
    return list(
        session.execute(
            select(CurriculumOffering.id)
            .join(
                CurriculumSubject,
                CurriculumSubject.id == CurriculumOffering.curriculum_subject_id,
            )
            .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
            .where(
                CurriculumOffering.tenant_id == tenant_id,
                CurriculumOffering.academic_term_id == academic_term_id,
                Curriculum.academic_level_id == academic_level_id,
                CurriculumSubject.is_active.is_(True),
            )
        ).scalars()
    )


def offering_ids_for_level_session(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    academic_level_id: uuid.UUID,
    academic_session_id: uuid.UUID,
) -> list[uuid.UUID]:
    from app.modules.student_academics.models import AcademicTerm

    return list(
        session.execute(
            select(CurriculumOffering.id)
            .join(
                CurriculumSubject,
                CurriculumSubject.id == CurriculumOffering.curriculum_subject_id,
            )
            .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
            .join(AcademicTerm, AcademicTerm.id == CurriculumOffering.academic_term_id)
            .where(
                CurriculumOffering.tenant_id == tenant_id,
                Curriculum.academic_level_id == academic_level_id,
                AcademicTerm.academic_session_id == academic_session_id,
                CurriculumSubject.is_active.is_(True),
            )
        ).scalars()
    )
