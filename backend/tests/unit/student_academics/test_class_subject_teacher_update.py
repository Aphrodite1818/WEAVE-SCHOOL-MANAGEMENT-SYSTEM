from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import ClassSubject, ClassSubjectTeacher
from app.modules.student_academics.schemas import ClassSubjectTeacherUpdate
from app.modules.student_academics.service import StudentAcademicService


def _assignment(tenant_id: uuid.UUID) -> ClassSubjectTeacher:
    return ClassSubjectTeacher(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        teacher_membership_id=uuid.uuid4(),
        is_core=True,
        sort_order=3,
        is_active=True,
    )


def _class_subject(tenant_id: uuid.UUID) -> ClassSubject:
    now = datetime.now(timezone.utc)
    return ClassSubject(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        is_core=True,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_class_subject_teacher_ignores_explicit_null_values() -> None:
    tenant_id = uuid.uuid4()
    assignment = _assignment(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_teacher_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_class_subject_teacher",
            new=AsyncMock(return_value=assignment),
        ),
    ):
        response = await StudentAcademicService.update_class_subject_teacher(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            payload=ClassSubjectTeacherUpdate(
                is_core=None,
                sort_order=None,
                is_active=None,
            ),
        )

    assert assignment.is_core is True
    assert assignment.sort_order == 3
    assert assignment.is_active is True
    assert response.is_core is True


@pytest.mark.asyncio
async def test_update_class_subject_teacher_applies_explicit_values() -> None:
    tenant_id = uuid.uuid4()
    assignment = _assignment(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_teacher_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_class_subject_teacher",
            new=AsyncMock(return_value=assignment),
        ),
    ):
        response = await StudentAcademicService.update_class_subject_teacher(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            payload=ClassSubjectTeacherUpdate(
                is_core=False,
                sort_order=7,
            ),
        )

    assert assignment.is_core is False
    assert assignment.sort_order == 7
    assert assignment.is_active is True
    assert response.sort_order == 7


@pytest.mark.asyncio
async def test_archive_class_subject_requires_ending_active_assignments() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_teacher_assignments_for_class_subject",
            new=AsyncMock(return_value=1),
        ),
    ):
        with pytest.raises(ConflictException):
            await StudentAcademicService.archive_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                admin_id=uuid.uuid4(),
            )


@pytest.mark.asyncio
async def test_restore_class_subject_returns_inactive_not_active() -> None:
    tenant_id = uuid.uuid4()
    class_subject = _class_subject(tenant_id)
    class_subject.is_active = False
    class_subject.archived_at = datetime.now(timezone.utc)
    class_subject.archived_by_admin_id = uuid.uuid4()
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_class_subject",
            new=AsyncMock(return_value=class_subject),
        ),
        patch(
            "app.modules.student_academics.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = await StudentAcademicService.restore_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=class_subject.id,
        )

    assert class_subject.archived_at is None
    assert class_subject.archived_by_admin_id is None
    assert class_subject.is_active is False
    assert response.is_active is False
