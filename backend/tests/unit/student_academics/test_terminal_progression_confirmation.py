from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.classes.repository import AcademicLevelRepository
from app.modules.student_academics.lifecycle_repository import StudentProgressionRepository
from app.modules.student_academics.progression_service import AcademicProgressionService
from app.modules.student_academics.session_closure_schemas import SessionClosureStartRequest
from app.modules.students.models import AcademicStatus
from app.modules.students.repository import StudentRepository


def test_session_closure_terminal_completion_is_opt_in() -> None:
    default_request = SessionClosureStartRequest(
        confirmation="START_SESSION_CLOSING",
        idempotency_key="closure-12345678",
    )
    confirmed_request = SessionClosureStartRequest(
        confirmation="START_SESSION_CLOSING",
        idempotency_key="closure-abcdefgh",
        allow_terminal_completion=True,
    )

    assert default_request.allow_terminal_completion is False
    assert confirmed_request.allow_terminal_completion is True


@pytest.mark.asyncio
async def test_terminal_student_cannot_be_graduated_without_confirmation(monkeypatch) -> None:
    tenant_id = uuid4()
    student_id = uuid4()
    level_id = uuid4()
    enrollment_id = uuid4()
    run_id = uuid4()

    enrollment = SimpleNamespace(
        id=enrollment_id,
        student_id=student_id,
        academic_level_id=level_id,
        class_id=None,
    )
    student = SimpleNamespace(
        id=student_id,
        is_archived=False,
        promotion_hold=False,
        status=AcademicStatus.ACTIVE,
    )
    level = SimpleNamespace(
        id=level_id,
        is_active=True,
        archived_at=None,
        name="Final Level",
    )
    actor = SimpleNamespace(id=uuid4(), tenant_id=tenant_id)
    run = SimpleNamespace(id=run_id)
    next_session = SimpleNamespace(id=uuid4())

    monkeypatch.setattr(
        StudentProgressionRepository,
        "get_item_by_run_and_student",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        StudentRepository,
        "get_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        AcademicLevelRepository,
        "get_by_id",
        AsyncMock(return_value=level),
    )
    monkeypatch.setattr(
        AcademicProgressionService,
        "resolve_next_level",
        AsyncMock(return_value=None),
    )

    with pytest.raises(ConflictException, match="explicit administrator confirmation"):
        await AcademicProgressionService._progress_student(
            AsyncMock(),
            actor=actor,
            run=run,
            enrollment=enrollment,
            next_session=next_session,
            effective_date=date(2026, 7, 31),
            allow_terminal_completion=False,
        )
