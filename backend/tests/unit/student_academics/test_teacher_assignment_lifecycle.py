from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.router import open_academic_term
from app.modules.student_academics.schemas import AcademicTermOpenRequest, TeacherAssignmentEnd
from app.modules.student_academics.service import StudentAcademicService
from app.modules.teachers.models import TeacherMembershipStatus
from app.modules.teachers.offboarding_service import (
    TeacherOffboardingRequest,
    TeacherOffboardingService,
)


@pytest.fixture(autouse=True)
def _allow_academic_writes_for_assignment_unit_tests():
    with patch(
        "app.modules.student_academics.service.ensure_academic_write_window",
        new=AsyncMock(),
    ):
        yield


def _assignment() -> TeacherAssignment:
    now = datetime.now(timezone.utc)
    return TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        curriculum_subject_id=uuid.uuid4(),
        teacher_membership_id=uuid.uuid4(),
        effective_from=date(2026, 1, 10),
        effective_to=None,
        created_at=now,
        updated_at=now,
    )


def _assignment_result(assignments: list[TeacherAssignment]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = assignments
    return result


@pytest.mark.asyncio
async def test_end_assignment_preserves_history() -> None:
    assignment = _assignment()
    db = AsyncMock()
    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._teacher_assignment_term_context",
            new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_backdated_assignment_change_safe",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._build_teacher_assignment_response",
            new=AsyncMock(return_value=SimpleNamespace(id=assignment.id)),
        ),
    ):
        await StudentAcademicService.end_teacher_assignment(
            db,
            assignment.tenant_id,
            assignment.id,
            TeacherAssignmentEnd(
                academic_term_id=uuid.uuid4(),
                effective_to=assignment.effective_from,
                reason="end assignment",
            ),
        )
    assert assignment.is_active is False
    assert assignment.effective_to == assignment.effective_from
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_historical_assignment_context_can_load_inactive_curriculum_subject() -> None:
    tenant_id = uuid.uuid4()
    curriculum_subject = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        curriculum_id=uuid.uuid4(),
        is_active=False,
    )
    curriculum = SimpleNamespace(
        id=curriculum_subject.curriculum_id,
        tenant_id=tenant_id,
    )
    result = MagicMock()
    result.first.return_value = (curriculum_subject, curriculum)
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    loaded_subject, loaded_curriculum = (
        await StudentAcademicService._load_curriculum_subject_context(
            db,
            tenant_id=tenant_id,
            curriculum_subject_id=curriculum_subject.id,
            require_active=False,
        )
    )

    assert loaded_subject is curriculum_subject
    assert loaded_curriculum is curriculum
    statement = db.execute.await_args.args[0]
    assert "curriculum_subjects.is_active" not in str(statement.whereclause)


@pytest.mark.asyncio
async def test_operational_assignment_context_requires_active_curriculum_subject() -> None:
    tenant_id = uuid.uuid4()
    result = MagicMock()
    result.first.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(Exception):
        await StudentAcademicService._load_curriculum_subject_context(
            db,
            tenant_id=tenant_id,
            curriculum_subject_id=uuid.uuid4(),
        )

    statement = db.execute.await_args.args[0]
    assert "curriculum_subjects.is_active" in str(statement.whereclause)


@pytest.mark.asyncio
async def test_open_academic_term_uses_canonical_academic_service() -> None:
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    term_id = uuid.uuid4()
    db = AsyncMock()
    admin = SimpleNamespace(tenant_id=tenant_id, id=admin_id)
    expected = SimpleNamespace(id=term_id)

    with patch(
        "app.modules.student_academics.router.StudentAcademicService.open_academic_term",
        new=AsyncMock(return_value=expected),
    ) as open_term:
        response = await open_academic_term(
            term_id,
            AcademicTermOpenRequest(confirmation="OPEN_ACADEMIC_TERM"),
            db,
            admin,
        )

    assert response is expected
    open_term.assert_awaited_once_with(db, tenant_id, term_id, admin_id)


@pytest.mark.asyncio
async def test_teacher_offboarding_ends_current_assignment_by_date() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id, id=admin_id)
    membership = SimpleNamespace(id=membership_id)
    assignment = TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=uuid.uuid4(),
        curriculum_subject_id=uuid.uuid4(),
        teacher_membership_id=membership_id,
        effective_from=today - timedelta(days=30),
        effective_to=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _assignment_result([assignment]),
                MagicMock(),
            ]
        )
    )
    expected = SimpleNamespace(id=membership_id)

    with (
        patch(
            "app.modules.teachers.offboarding_service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.teachers.offboarding_service.TeacherMembershipRepository.get_by_id",
            new=AsyncMock(return_value=membership),
        ),
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(return_value=assignment),
        ) as save_assignment,
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicRepository.delete_teacher_assignment",
            new=AsyncMock(),
        ) as delete_assignment,
        patch(
            "app.modules.teachers.offboarding_service.TeacherOffboardingService._create_replacement_assignment",
            new=AsyncMock(),
        ) as create_replacement,
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ) as record_audit,
        patch(
            "app.modules.teachers.offboarding_service.TeacherMembershipService.end_membership",
            new=AsyncMock(return_value=expected),
        ) as end_membership,
    ):
        response = await TeacherOffboardingService.end_membership_and_release_responsibilities(
            db,
            actor=actor,
            membership_id=membership_id,
            payload=TeacherOffboardingRequest(reason="Teacher left the school"),
        )

    assert response is expected
    assert assignment.effective_to == today
    save_assignment.assert_awaited_once_with(db, assignment)
    delete_assignment.assert_not_awaited()
    create_replacement.assert_not_awaited()
    record_audit.assert_awaited_once()
    end_membership.assert_awaited_once()


@pytest.mark.asyncio
async def test_teacher_offboarding_transfers_scheduled_assignment_temporally() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    replacement_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id, id=admin_id)
    membership = SimpleNamespace(id=membership_id)
    replacement_membership = SimpleNamespace(
        id=replacement_id,
        status=TeacherMembershipStatus.ACTIVE,
    )
    scheduled = TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=uuid.uuid4(),
        curriculum_subject_id=uuid.uuid4(),
        teacher_membership_id=membership_id,
        effective_from=today + timedelta(days=10),
        effective_to=today + timedelta(days=40),
    )
    replacement_assignment = TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=scheduled.class_id,
        curriculum_subject_id=scheduled.curriculum_subject_id,
        teacher_membership_id=replacement_id,
        effective_from=scheduled.effective_from,
        effective_to=scheduled.effective_to,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _assignment_result([scheduled]),
                MagicMock(),
            ]
        )
    )
    expected = SimpleNamespace(id=membership_id)

    with (
        patch(
            "app.modules.teachers.offboarding_service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.teachers.offboarding_service.TeacherMembershipRepository.get_by_id",
            new=AsyncMock(side_effect=[membership, replacement_membership]),
        ),
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicService._validate_teacher_capability",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicRepository.delete_teacher_assignment",
            new=AsyncMock(),
        ) as delete_assignment,
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(),
        ) as save_assignment,
        patch(
            "app.modules.teachers.offboarding_service.TeacherOffboardingService._create_replacement_assignment",
            new=AsyncMock(return_value=replacement_assignment),
        ) as create_replacement,
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ) as record_audit,
        patch(
            "app.modules.teachers.offboarding_service.TeacherMembershipService.end_membership",
            new=AsyncMock(return_value=expected),
        ),
    ):
        response = await TeacherOffboardingService.end_membership_and_release_responsibilities(
            db,
            actor=actor,
            membership_id=membership_id,
            payload=TeacherOffboardingRequest(
                reason="Teacher left the school",
                replacement_teacher_membership_id=replacement_id,
            ),
        )

    assert response is expected
    delete_assignment.assert_awaited_once_with(db, scheduled)
    save_assignment.assert_not_awaited()
    create_replacement.assert_awaited_once_with(
        db,
        tenant_id=tenant_id,
        source=scheduled,
        replacement_teacher_membership_id=replacement_id,
        effective_from=scheduled.effective_from,
        effective_to=scheduled.effective_to,
    )
    record_audit.assert_awaited_once()
