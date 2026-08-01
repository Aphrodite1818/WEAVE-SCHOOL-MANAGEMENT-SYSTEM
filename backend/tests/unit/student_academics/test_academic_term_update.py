from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestException, ConflictException
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermName,
    AcademicTermStatus,
)
from app.modules.student_academics.schemas import (
    AcademicTermCreate,
    AcademicTermDependencyPreview,
    AcademicTermUpdate,
)
from app.modules.student_academics.service import StudentAcademicService


def _academic_session(
    tenant_id: uuid.UUID,
    *,
    status: AcademicSessionStatus = AcademicSessionStatus.OPEN,
) -> AcademicSession:
    return AcademicSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="2026/2027",
        status=status,
        is_current=status == AcademicSessionStatus.OPEN,
    )


def _academic_term(
    tenant_id: uuid.UUID,
    *,
    academic_session_id: uuid.UUID | None = None,
    status: AcademicTermStatus = AcademicTermStatus.DRAFT,
) -> AcademicTerm:
    return AcademicTerm(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        academic_session_id=academic_session_id or uuid.uuid4(),
        name=AcademicTermName.FIRST_TERM,
        start_date=date(2026, 1, 12),
        end_date=date(2026, 4, 10),
        status=status,
        is_current=status == AcademicTermStatus.OPEN,
    )


@pytest.mark.asyncio
async def test_create_academic_term_is_always_draft() -> None:
    tenant_id = uuid.uuid4()
    session = _academic_session(tenant_id)
    db = AsyncMock()

    async def save_term(_db, term):
        return term

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_id",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_term_by_session_and_name",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.create_academic_term",
            new=AsyncMock(side_effect=save_term),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.add_academic_lifecycle_audit",
            new=AsyncMock(),
        ),
    ):
        created = await StudentAcademicService.create_academic_term(
            db=db,
            tenant_id=tenant_id,
            payload=AcademicTermCreate(
                academic_session_id=session.id,
                name=AcademicTermName.FIRST_TERM,
            ),
        )

    assert created.status == AcademicTermStatus.DRAFT
    assert created.is_current is False


@pytest.mark.asyncio
async def test_update_academic_term_allows_explicit_nullable_dates_to_clear() -> None:
    tenant_id = uuid.uuid4()
    term = _academic_term(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_term_by_id",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_id",
            new=AsyncMock(return_value=_academic_session(tenant_id)),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_academic_term",
            new=AsyncMock(return_value=term),
        ) as save_term,
    ):
        updated = await StudentAcademicService.update_academic_term(
            db=db,
            tenant_id=tenant_id,
            term_id=term.id,
            payload=AcademicTermUpdate(
                name=None,
                start_date=None,
                end_date=None,
            ),
        )

    assert updated is term
    assert term.name == AcademicTermName.FIRST_TERM
    assert term.start_date is None
    assert term.end_date is None
    assert term.is_current is False
    assert term.status == AcademicTermStatus.DRAFT
    save_term.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_academic_term_rejects_open_term() -> None:
    tenant_id = uuid.uuid4()
    term = _academic_term(tenant_id, status=AcademicTermStatus.OPEN)
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_term_by_id",
        new=AsyncMock(return_value=term),
    ):
        with pytest.raises(ConflictException):
            await StudentAcademicService.update_academic_term(
                db=db,
                tenant_id=tenant_id,
                term_id=term.id,
                payload=AcademicTermUpdate(start_date=date(2026, 1, 15)),
            )


@pytest.mark.asyncio
async def test_update_academic_term_rejects_invalid_effective_date_range() -> None:
    tenant_id = uuid.uuid4()
    term = _academic_term(tenant_id)
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_term_by_id",
        new=AsyncMock(return_value=term),
    ), patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_id",
        new=AsyncMock(return_value=_academic_session(tenant_id)),
    ):
        with pytest.raises(BadRequestException):
            await StudentAcademicService.update_academic_term(
                db=db,
                tenant_id=tenant_id,
                term_id=term.id,
                payload=AcademicTermUpdate(start_date=date(2026, 4, 11)),
            )


@pytest.mark.asyncio
async def test_open_academic_term_sets_current_only_for_draft_terms() -> None:
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    session = _academic_session(tenant_id)
    term = _academic_term(tenant_id, academic_session_id=session.id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_term_by_id",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_id",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_current_term",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_terms_by_session",
            new=AsyncMock(return_value=([term], 1)),
        ),
        patch(
            "app.modules.school_calendar.service.SchoolCalendarService.term_calendar_readiness",
            new=AsyncMock(return_value={"blockers": [], "counts": {}, "calendar_id": str(uuid.uuid4())}),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_academic_term",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.add_academic_lifecycle_audit",
            new=AsyncMock(),
        ),
    ):
        opened = await StudentAcademicService.open_academic_term(
            db=db,
            tenant_id=tenant_id,
            term_id=term.id,
            admin_id=admin_id,
        )

    assert opened.status == AcademicTermStatus.OPEN
    assert opened.is_current is True
    assert opened.opened_by_admin_id == admin_id
    assert opened.opened_at is not None
    assert opened.closing_started_at is None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_academic_term_starts_closure_for_open_terms() -> None:
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    term = _academic_term(tenant_id, status=AcademicTermStatus.OPEN)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_term_by_id",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_academic_term",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService.academic_term_dependency_preview",
            new=AsyncMock(
                return_value=AcademicTermDependencyPreview(
                    term_id=term.id,
                    dependency_counts={},
                    blocker_messages=[],
                    can_open=False,
                    can_close=True,
                    can_delete=False,
                )
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.add_academic_lifecycle_audit",
            new=AsyncMock(),
        ),
    ):
        closing = await StudentAcademicService.close_academic_term(
            db=db,
            tenant_id=tenant_id,
            term_id=term.id,
            admin_id=admin_id,
        )

    assert closing.status == AcademicTermStatus.CLOSING
    assert closing.is_current is True
    assert closing.closing_started_at is not None
    assert closing.closed_by_admin_id is None
    assert closing.closed_at is None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_academic_term_closure_closes_and_archives_calendar() -> None:
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    term = _academic_term(tenant_id, status=AcademicTermStatus.CLOSING)
    db = AsyncMock()

    archive_calendar = AsyncMock(return_value=1)

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_term_by_id",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_academic_term",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService.academic_term_dependency_preview",
            new=AsyncMock(
                return_value=AcademicTermDependencyPreview(
                    term_id=term.id,
                    dependency_counts={},
                    blocker_messages=[],
                    can_open=False,
                    can_close=True,
                    can_finalize_close=True,
                    can_delete=False,
                )
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.add_academic_lifecycle_audit",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.school_calendar.service.SchoolCalendarService.archive_term_calendar",
            new=archive_calendar,
        ),
    ):
        closed = await StudentAcademicService.finalize_academic_term_closure(
            db=db,
            tenant_id=tenant_id,
            term_id=term.id,
            admin_id=admin_id,
        )

    assert closed.status == AcademicTermStatus.CLOSED
    assert closed.is_current is False
    assert closed.closed_by_admin_id == admin_id
    assert closed.closed_at is not None
    archive_calendar.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_academic_term_rejects_closed_terms() -> None:
    tenant_id = uuid.uuid4()
    term = _academic_term(tenant_id, status=AcademicTermStatus.CLOSED)
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_term_by_id",
        new=AsyncMock(return_value=term),
    ):
        with pytest.raises(ConflictException):
            await StudentAcademicService.close_academic_term(
                db=db,
                tenant_id=tenant_id,
                term_id=term.id,
                admin_id=uuid.uuid4(),
            )
