from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    StudentProgressionItem,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
    StudentProgressionRun,
    StudentProgressionRunStatus,
)
from app.modules.student_academics.progression_service import AcademicProgressionService
from app.modules.student_academics.session_closure_service import SessionClosureService
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.students.models import StudentEnrollment


def _session(
    tenant_id: uuid.UUID,
    *,
    name: str,
    start_date: date | None,
    end_date: date | None,
    status: AcademicSessionStatus = AcademicSessionStatus.DRAFT,
    is_current: bool = False,
) -> AcademicSession:
    return AcademicSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        start_date=start_date,
        end_date=end_date,
        status=status,
        is_current=is_current,
    )


def _run(
    tenant_id: uuid.UUID,
    *,
    status: StudentProgressionRunStatus,
    started_at: datetime | None,
) -> StudentProgressionRun:
    return StudentProgressionRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        academic_session_id=uuid.uuid4(),
        next_academic_session_id=uuid.uuid4(),
        idempotency_key=f"test-{uuid.uuid4()}",
        status=status,
        started_at=started_at,
    )


def test_academic_session_model_exposes_hardening_constraints() -> None:
    constraint_names = {
        constraint.name
        for constraint in AcademicSession.__table__.constraints
        if constraint.name is not None
    }

    assert "ck_academic_session_current_matches_status" in constraint_names
    assert "ck_academic_session_date_range" in constraint_names
    assert "ck_academic_session_operational_dates" in constraint_names
    assert "excl_academic_sessions_date_overlap" in constraint_names


def test_next_session_dates_accept_strictly_later_complete_range() -> None:
    tenant_id = uuid.uuid4()
    current = _session(
        tenant_id,
        name="2026/2027",
        start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31),
        status=AcademicSessionStatus.OPEN,
        is_current=True,
    )
    next_session = _session(
        tenant_id,
        name="2027/2028",
        start_date=date(2027, 9, 1),
        end_date=date(2028, 7, 31),
    )

    assert (
        SessionClosureService._next_session_date_blockers(
            session=current,
            next_session=next_session,
        )
        == []
    )


def test_next_session_dates_reject_missing_range() -> None:
    tenant_id = uuid.uuid4()
    current = _session(
        tenant_id,
        name="2026/2027",
        start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31),
        status=AcademicSessionStatus.OPEN,
        is_current=True,
    )
    next_session = _session(
        tenant_id,
        name="2027/2028",
        start_date=None,
        end_date=None,
    )

    blockers = SessionClosureService._next_session_date_blockers(
        session=current,
        next_session=next_session,
    )

    assert any("next academic session" in message.lower() for message in blockers)


def test_next_session_dates_reject_touching_or_overlapping_range() -> None:
    tenant_id = uuid.uuid4()
    current = _session(
        tenant_id,
        name="2026/2027",
        start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31),
        status=AcademicSessionStatus.OPEN,
        is_current=True,
    )
    next_session = _session(
        tenant_id,
        name="2027/2028",
        start_date=date(2027, 7, 31),
        end_date=date(2028, 7, 31),
    )

    blockers = SessionClosureService._next_session_date_blockers(
        session=current,
        next_session=next_session,
    )

    assert any("start after" in message.lower() for message in blockers)


def test_processing_run_becomes_recoverable_only_after_stale_threshold() -> None:
    tenant_id = uuid.uuid4()
    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    fresh = _run(
        tenant_id,
        status=StudentProgressionRunStatus.PROCESSING,
        started_at=now - timedelta(minutes=30),
    )
    stale = _run(
        tenant_id,
        status=StudentProgressionRunStatus.PROCESSING,
        started_at=now - timedelta(minutes=66),
    )
    pending = _run(
        tenant_id,
        status=StudentProgressionRunStatus.PENDING,
        started_at=None,
    )

    assert SessionClosureService._processing_is_stale(fresh, now=now) is False
    assert SessionClosureService._processing_is_stale(stale, now=now) is True
    assert SessionClosureService._processing_is_stale(pending, now=now) is False


@pytest.mark.asyncio
async def test_initial_progression_enqueue_treats_existing_job_as_dispatched() -> None:
    tenant_id = uuid.uuid4()
    run = _run(
        tenant_id,
        status=StudentProgressionRunStatus.PENDING,
        started_at=None,
    )

    with patch(
        "app.core.queue.arq.enqueue_session_progression_job",
        new=AsyncMock(return_value=False),
    ):
        queued = await SessionClosureService._enqueue_progression_safely(
            run=run,
            tenant_id=tenant_id,
        )

    assert queued is True


@pytest.mark.asyncio
async def test_progression_enqueue_failure_leaves_request_recoverable() -> None:
    tenant_id = uuid.uuid4()
    run = _run(
        tenant_id,
        status=StudentProgressionRunStatus.PENDING,
        started_at=None,
    )

    with patch(
        "app.core.queue.arq.enqueue_session_progression_job",
        new=AsyncMock(side_effect=RuntimeError("redis unavailable")),
    ):
        queued = await SessionClosureService._enqueue_progression_safely(
            run=run,
            tenant_id=tenant_id,
        )

    assert queued is False


@pytest.mark.asyncio
async def test_write_guard_acquires_lifecycle_lock_before_reading_session_state() -> None:
    tenant_id = uuid.uuid4()
    events: list[str] = []
    db = AsyncMock()
    result = MagicMock()
    result.first.return_value = None

    async def acquire_lock(*_args, **_kwargs) -> None:
        events.append("lock")

    async def execute_query(*_args, **_kwargs):
        events.append("query")
        return result

    db.execute.side_effect = execute_query

    with patch(
        "app.modules.student_academics.write_guard.acquire_academic_lifecycle_lock",
        new=AsyncMock(side_effect=acquire_lock),
    ):
        await ensure_academic_write_window(db, tenant_id=tenant_id)

    assert events == ["lock", "query"]


@pytest.mark.asyncio
async def test_blocked_progression_item_is_reprocessed_on_retry() -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    level_id = uuid.uuid4()
    class_id = uuid.uuid4()
    current_session_id = uuid.uuid4()
    run = _run(
        tenant_id,
        status=StudentProgressionRunStatus.PROCESSING,
        started_at=datetime.now(timezone.utc),
    )
    enrollment = StudentEnrollment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        student_id=student_id,
        academic_level_id=level_id,
        class_id=class_id,
        academic_session_id=current_session_id,
        started_on=date(2026, 9, 1),
    )
    blocked = StudentProgressionItem(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        progression_run_id=run.id,
        student_id=student_id,
        from_enrollment_id=enrollment.id,
        from_level_id=level_id,
        from_class_id=class_id,
        action=StudentProgressionItemAction.SKIP,
        status=StudentProgressionItemStatus.BLOCKED,
        reason="temporary failure",
    )
    next_session = _session(
        tenant_id,
        name="2027/2028",
        start_date=date(2027, 9, 1),
        end_date=date(2028, 7, 31),
    )
    actor = MagicMock()
    actor.id = uuid.uuid4()
    actor.tenant_id = tenant_id
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.progression_service.StudentProgressionRepository.get_item_by_run_and_student",
            new=AsyncMock(return_value=blocked),
        ),
        patch(
            "app.modules.student_academics.progression_service.StudentRepository.get_by_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        with pytest.raises(ConflictException):
            await AcademicProgressionService._progress_student(
                db,
                actor=actor,
                run=run,
                enrollment=enrollment,
                next_session=next_session,
                effective_date=date(2027, 7, 31),
            )
