"""Stable CBT projections for subjects, curricula, and current-term offerings."""

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
from app.modules.classes.models import AcademicLevel, ClassRoom, Department
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumOffering,
    CurriculumSubject,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermStatus,
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
    joined = session.execute(
        select(Curriculum, AcademicLevel)
        .join(AcademicLevel, AcademicLevel.id == Curriculum.academic_level_id)
        .where(
            Curriculum.tenant_id == tenant_id,
            Curriculum.id == entity_id,
            AcademicLevel.tenant_id == tenant_id,
        )
    ).first()
    if joined is None:
        return None
    curriculum, level = joined
    if not _visible(level):
        return None
    return CBTCurriculumSnapshot(
        id=curriculum.id,
        academic_level_id=curriculum.academic_level_id,
    ).model_dump(mode="json")


def project_curriculum_subject(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    joined = session.execute(
        select(CurriculumSubject, Curriculum, AcademicLevel, Subject)
        .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
        .join(AcademicLevel, AcademicLevel.id == Curriculum.academic_level_id)
        .join(Subject, Subject.id == CurriculumSubject.subject_id)
        .where(
            CurriculumSubject.tenant_id == tenant_id,
            CurriculumSubject.id == entity_id,
            Curriculum.tenant_id == tenant_id,
            AcademicLevel.tenant_id == tenant_id,
            Subject.tenant_id == tenant_id,
        )
    ).first()
    if joined is None:
        return None
    curriculum_subject, _curriculum, level, subject = joined
    if not _visible(curriculum_subject) or not _visible(level) or not _visible(subject):
        return None
    return CBTCurriculumSubjectSnapshot(
        id=curriculum_subject.id,
        curriculum_id=curriculum_subject.curriculum_id,
        subject_id=curriculum_subject.subject_id,
        is_elective=curriculum_subject.is_elective,
        is_active=curriculum_subject.is_active,
    ).model_dump(mode="json")


def _eligible_enrollment_ids(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    academic_level_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    department_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    term = session.execute(
        select(AcademicTerm, AcademicSession)
        .join(AcademicSession, AcademicSession.id == AcademicTerm.academic_session_id)
        .where(
            AcademicTerm.tenant_id == tenant_id,
            AcademicTerm.id == academic_term_id,
            AcademicSession.tenant_id == tenant_id,
        )
    ).first()
    if term is None:
        return []
    academic_term, academic_session = term
    if (
        not academic_session.is_current
        or academic_session.status
        not in {AcademicSessionStatus.OPEN, AcademicSessionStatus.CLOSING}
        or not academic_term.is_current
        or academic_term.status != AcademicTermStatus.OPEN
    ):
        return []

    enrollment_rows = list(
        session.execute(
            select(StudentEnrollment.id, StudentEnrollment.class_id)
            .join(Student, Student.id == StudentEnrollment.student_id)
            .join(ClassRoom, ClassRoom.id == StudentEnrollment.class_id)
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.academic_level_id == academic_level_id,
                StudentEnrollment.academic_session_id == academic_term.academic_session_id,
                StudentEnrollment.is_current.is_(True),
                Student.status == AcademicStatus.ACTIVE,
                Student.is_archived.is_(False),
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.academic_level_id == academic_level_id,
                ClassRoom.is_active.is_(True),
                ClassRoom.archived_at.is_(None),
            )
        ).all()
    )
    if department_id is None:
        return [row.id for row in enrollment_rows]

    department = session.execute(
        select(Department).where(
            Department.tenant_id == tenant_id,
            Department.id == department_id,
        )
    ).scalar_one_or_none()
    if not _visible(department) or department.academic_level_id != academic_level_id:
        return []

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
        select(
            CurriculumOffering,
            CurriculumSubject,
            Curriculum,
            AcademicLevel,
            Subject,
            AcademicTerm,
            AcademicSession,
        )
        .join(
            CurriculumSubject,
            CurriculumSubject.id == CurriculumOffering.curriculum_subject_id,
        )
        .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
        .join(AcademicLevel, AcademicLevel.id == Curriculum.academic_level_id)
        .join(Subject, Subject.id == CurriculumSubject.subject_id)
        .join(AcademicTerm, AcademicTerm.id == CurriculumOffering.academic_term_id)
        .join(AcademicSession, AcademicSession.id == AcademicTerm.academic_session_id)
        .where(
            CurriculumOffering.tenant_id == tenant_id,
            CurriculumOffering.id == entity_id,
            CurriculumSubject.tenant_id == tenant_id,
            Curriculum.tenant_id == tenant_id,
            AcademicLevel.tenant_id == tenant_id,
            Subject.tenant_id == tenant_id,
            AcademicTerm.tenant_id == tenant_id,
            AcademicSession.tenant_id == tenant_id,
        )
    ).first()
    if joined is None:
        return None
    offering, curriculum_subject, curriculum, level, subject, term, academic_session = joined
    if (
        not _visible(curriculum_subject)
        or not _visible(level)
        or not _visible(subject)
        or not academic_session.is_current
        or academic_session.status
        not in {AcademicSessionStatus.OPEN, AcademicSessionStatus.CLOSING}
        or not term.is_current
        or term.status != AcademicTermStatus.OPEN
    ):
        return None

    if offering.department_id is not None:
        department = session.execute(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.id == offering.department_id,
            )
        ).scalar_one_or_none()
        if not _visible(department) or department.academic_level_id != curriculum.academic_level_id:
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
