from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.students.lifecycle_service import StudentLifecycleService
from app.modules.students.models import (
    AcademicStatus,
    StudentAccountStatus,
    StudentEnrollmentOutcome,
)
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository


@pytest.mark.parametrize(
    "status",
    [
        AcademicStatus.WITHDRAWN,
        AcademicStatus.EXPELLED,
        AcademicStatus.GRADUATED,
    ],
)
@pytest.mark.asyncio
async def test_terminal_exit_enrollment_is_not_mistaken_for_due_return(
    monkeypatch,
    status,
) -> None:
    tenant_id = uuid4()
    student = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        admission_number="STD-TERMINAL",
        status=status,
        promotion_hold=True,
        is_active=False,
        account_status=StudentAccountStatus.INACTIVE,
        graduation_date=date.today() if status == AcademicStatus.GRADUATED else None,
    )
    terminal_enrollment = SimpleNamespace(
        id=uuid4(),
        ended_on=date.today(),
        exit_outcome=StudentEnrollmentOutcome(status.value),
    )
    get_current = AsyncMock(return_value=terminal_enrollment)
    save_student = AsyncMock()
    monkeypatch.setattr(StudentEnrollmentRepository, "get_current", get_current)
    monkeypatch.setattr(StudentRepository, "save", save_student)

    db = SimpleNamespace(
        execute=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    changed = await StudentLifecycleService.activate_due_return(
        db,
        student=student,
        commit=False,
    )

    assert changed is False
    assert student.status == status
    assert student.is_active is False
    assert student.account_status == StudentAccountStatus.INACTIVE
    get_current.assert_awaited_once_with(
        db,
        tenant_id,
        student.id,
        lock=True,
    )
    save_student.assert_not_awaited()
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_due_return_enrollment_still_materializes_active_state(monkeypatch) -> None:
    tenant_id = uuid4()
    student = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        admission_number="STD-DUE-RETURN",
        status=AcademicStatus.WITHDRAWN,
        promotion_hold=True,
        is_active=False,
        account_status=StudentAccountStatus.INACTIVE,
        graduation_date=None,
    )
    return_enrollment = SimpleNamespace(id=uuid4(), ended_on=None)
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=return_enrollment),
    )
    save_student = AsyncMock()
    monkeypatch.setattr(StudentRepository, "save", save_student)
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AuthIdentityService.ensure_for_actor",
        AsyncMock(),
    )
    restore_links = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(
        StudentLifecycleService,
        "_restore_parent_links_after_return",
        restore_links,
    )

    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: None)
        ),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    changed = await StudentLifecycleService.activate_due_return(
        db,
        student=student,
        commit=False,
    )

    assert changed is True
    assert student.status == AcademicStatus.ACTIVE
    assert student.promotion_hold is False
    assert student.is_active is True
    assert student.account_status == StudentAccountStatus.ACTIVE
    save_student.assert_awaited_once_with(db, student)
    restore_links.assert_awaited_once()
