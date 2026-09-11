"""Database regression tests for canonical departments and level mappings."""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.classes.models import (
    AcademicCategory,
    AcademicLevel,
    AcademicLevelDepartment,
    AcademicLevelStatus,
    ArmLabel,
    ClassRoom,
    Department,
)
from app.modules.classes.department_repository import AcademicLevelDepartmentRepository
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumSubject,
    CurriculumSubjectDepartment,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermName,
    AcademicTermStatus,
)
from app.modules.subjects.models import Subject
from app.tenant_management.models import Tenant


@pytest.mark.asyncio
async def test_one_canonical_department_can_be_mapped_to_different_levels(
    db_session: AsyncSession,
    tenant: Tenant,
) -> None:
    first_level = AcademicLevel(
        tenant_id=tenant.id,
        name="SS1",
        normalized_name="ss1",
        category=AcademicCategory.SENIOR_SECONDARY,
        position=1,
        status=AcademicLevelStatus.ACTIVE,
    )
    second_level = AcademicLevel(
        tenant_id=tenant.id,
        name="SS2",
        normalized_name="ss2",
        category=AcademicCategory.SENIOR_SECONDARY,
        position=2,
        status=AcademicLevelStatus.ACTIVE,
    )
    db_session.add_all([first_level, second_level])
    await db_session.flush()

    department = Department(
        tenant_id=tenant.id,
        name="Science",
        normalized_name="science",
        is_active=True,
    )
    db_session.add(department)
    await db_session.flush()
    db_session.add_all(
        [
            AcademicLevelDepartment(
                tenant_id=tenant.id,
                academic_level_id=first_level.id,
                department_id=department.id,
                is_active=True,
            ),
            AcademicLevelDepartment(
                tenant_id=tenant.id,
                academic_level_id=second_level.id,
                department_id=department.id,
                is_active=True,
            ),
        ]
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_same_department_mapping_is_rejected_twice_on_same_level(
    db_session: AsyncSession,
    tenant: Tenant,
) -> None:
    level = AcademicLevel(
        tenant_id=tenant.id,
        name="SS1",
        normalized_name="ss1",
        category=AcademicCategory.SENIOR_SECONDARY,
        position=1,
        status=AcademicLevelStatus.ACTIVE,
    )
    db_session.add(level)
    await db_session.flush()

    department = Department(
        tenant_id=tenant.id,
        name="Science",
        normalized_name="science",
        is_active=True,
    )
    db_session.add(department)
    await db_session.flush()

    db_session.add(
        AcademicLevelDepartment(
            tenant_id=tenant.id,
            academic_level_id=level.id,
            department_id=department.id,
            is_active=True,
        )
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                AcademicLevelDepartment(
                    tenant_id=tenant.id,
                    academic_level_id=level.id,
                    department_id=department.id,
                    is_active=True,
                )
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_department_dependency_snapshot_splits_live_and_historical_terms(
    db_session: AsyncSession,
    tenant: Tenant,
) -> None:
    level_id = uuid4()
    department_id = uuid4()
    level_department_id = uuid4()
    arm_id = uuid4()
    subject_id = uuid4()
    level = AcademicLevel(
        id=level_id,
        tenant_id=tenant.id,
        name="SS1",
        normalized_name="ss1",
        category=AcademicCategory.SENIOR_SECONDARY,
        position=1,
        status=AcademicLevelStatus.ACTIVE,
    )
    department = Department(
        id=department_id,
        tenant_id=tenant.id,
        name="Science",
        normalized_name="science",
        is_active=True,
    )
    arm = ArmLabel(
        id=arm_id,
        tenant_id=tenant.id,
        label="A",
        normalized_label="a",
        is_active=True,
    )
    subject = Subject(
        id=subject_id,
        tenant_id=tenant.id,
        name="Physics",
        normalized_name="physics",
        code="PHY",
        normalized_code="phy",
        is_active=True,
    )
    db_session.add_all([level, department, arm, subject])
    await db_session.flush()

    level_department = AcademicLevelDepartment(
        id=level_department_id,
        tenant_id=tenant.id,
        academic_level_id=level_id,
        department_id=department_id,
        is_active=True,
    )
    db_session.add(level_department)
    await db_session.flush()

    classroom = ClassRoom(
        tenant_id=tenant.id,
        academic_level_id=level_id,
        arm_label_id=arm_id,
        is_active=True,
    )
    curriculum = Curriculum(tenant_id=tenant.id, academic_level_id=level_id)
    db_session.add_all([classroom, curriculum])
    await db_session.flush()

    curriculum_subject = CurriculumSubject(
        tenant_id=tenant.id,
        curriculum_id=curriculum.id,
        subject_id=subject.id,
        is_active=True,
    )
    db_session.add(curriculum_subject)
    await db_session.flush()

    terms = [_term(tenant.id, status) for status in AcademicTermStatus]
    db_session.add_all([term[0] for term in terms])
    await db_session.flush()
    db_session.add_all([term[1] for term in terms])
    await db_session.flush()

    db_session.add_all(
        [
            ClassTermDepartmentAssignment(
                tenant_id=tenant.id,
                class_id=classroom.id,
                academic_term_id=term.id,
                academic_level_department_id=level_department_id,
            )
            for _, term in terms
        ]
        + [
            CurriculumSubjectDepartment(
                tenant_id=tenant.id,
                curriculum_subject_id=curriculum_subject.id,
                academic_level_department_id=level_department_id,
            )
        ]
    )
    await db_session.flush()

    counts = await AcademicLevelDepartmentRepository.count_dependencies(
        db_session,
        tenant.id,
        level_department_id,
    )

    assert counts == {
        "class_assignments_total": 4,
        "class_assignments_live": 3,
        "curriculum_subject_links_total": 1,
        "curriculum_subject_links_live": 1,
    }


def _term(
    tenant_id,
    status: AcademicTermStatus,
) -> tuple[AcademicSession, AcademicTerm]:
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    index = list(AcademicTermStatus).index(status)
    session_start = date(2026 + index, 1, 1)
    session_end = date(2026 + index, 12, 31)
    session = AcademicSession(
        id=session_id,
        tenant_id=tenant_id,
        name=f"2026/{status.value}",
        start_date=session_start,
        end_date=session_end,
        status=AcademicSessionStatus.CLOSED,
        is_current=False,
        closing_started_at=now,
        closed_at=now,
    )
    term = AcademicTerm(
        tenant_id=tenant_id,
        academic_session_id=session_id,
        name=AcademicTermName.FIRST_TERM,
        start_date=date(2026 + index, 1, 1),
        end_date=date(2026 + index, 3, 31),
        status=status,
        is_current=False,
    )
    if status in {
        AcademicTermStatus.OPEN,
        AcademicTermStatus.CLOSING,
        AcademicTermStatus.CLOSED,
    }:
        term.opened_at = now
    if status in {AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED}:
        term.closing_started_at = now
    if status == AcademicTermStatus.CLOSED:
        term.closed_at = now
    return session, term
