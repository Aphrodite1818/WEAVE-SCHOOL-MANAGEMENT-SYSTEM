from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.student_academics.models import ClassSubjectTeacher
from app.modules.student_academics.schemas import ClassSubjectTeacherUpdate
from app.modules.student_academics.service_impl import StudentAcademicService


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


@pytest.mark.asyncio
async def test_update_class_subject_teacher_ignores_explicit_null_values() -> None:
    tenant_id = uuid.uuid4()
    assignment = _assignment(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service_impl.StudentAcademicRepository.get_class_subject_teacher_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service_impl.StudentAcademicRepository.save_class_subject_teacher",
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
            "app.modules.student_academics.service_impl.StudentAcademicRepository.get_class_subject_teacher_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service_impl.StudentAcademicRepository.save_class_subject_teacher",
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
