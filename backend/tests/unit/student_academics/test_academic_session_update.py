from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestException, ConflictException
from app.modules.student_academics.models import AcademicSession, AcademicSessionStatus
from app.modules.student_academics.schemas import AcademicSessionUpdate
from app.modules.student_academics.service import StudentAcademicService


def _session(tenant_id: uuid.UUID) -> AcademicSession:
    return AcademicSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="2026/2027",
        start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31),
        status=AcademicSessionStatus.DRAFT,
        is_current=False,
    )


def test_update_academic_session_rejects_explicit_null_name() -> None:
    with pytest.raises(ValidationError):
        AcademicSessionUpdate(name=None)


@pytest.mark.asyncio
async def test_update_academic_session_allows_explicit_nullable_fields_to_clear() -> None:
    tenant_id = uuid.uuid4()
    session = _session(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_id",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_academic_session",
            new=AsyncMock(return_value=session),
        ),
    ):
        updated = await StudentAcademicService.update_academic_session(
            db=db,
            tenant_id=tenant_id,
            academic_session_id=session.id,
            payload=AcademicSessionUpdate(
                start_date=None,
                end_date=None,
                next_academic_session_id=None,
            ),
        )

    assert updated is session
    assert session.name == "2026/2027"
    assert session.start_date is None
    assert session.end_date is None
    assert session.next_academic_session_id is None


@pytest.mark.asyncio
async def test_update_academic_session_applies_explicit_values() -> None:
    tenant_id = uuid.uuid4()
    session = _session(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_id",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_name",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_academic_session",
            new=AsyncMock(return_value=session),
        ),
    ):
        updated = await StudentAcademicService.update_academic_session(
            db=db,
            tenant_id=tenant_id,
            academic_session_id=session.id,
            payload=AcademicSessionUpdate(name="2027/2028"),
        )

    assert updated.name == "2027/2028"


@pytest.mark.asyncio
async def test_update_academic_session_rejects_invalid_effective_date_range() -> None:
    tenant_id = uuid.uuid4()
    session = _session(tenant_id)
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_id",
        new=AsyncMock(return_value=session),
    ):
        with pytest.raises(BadRequestException):
            await StudentAcademicService.update_academic_session(
                db=db,
                tenant_id=tenant_id,
                academic_session_id=session.id,
                payload=AcademicSessionUpdate(start_date=date(2028, 1, 1)),
            )


@pytest.mark.asyncio
async def test_update_open_academic_session_allows_next_session_configuration() -> None:
    tenant_id = uuid.uuid4()
    session = _session(tenant_id)
    session.status = AcademicSessionStatus.OPEN
    session.is_current = True
    next_session = AcademicSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="2027/2028",
        start_date=date(2027, 9, 1),
        end_date=date(2028, 7, 31),
        status=AcademicSessionStatus.DRAFT,
        is_current=False,
    )
    db = AsyncMock()

    async def get_by_id(_db, _tenant_id, session_id, **_kwargs):
        if session_id == session.id:
            return session
        if session_id == next_session.id:
            return next_session
        return None

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_id",
            new=AsyncMock(side_effect=get_by_id),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_academic_session",
            new=AsyncMock(return_value=session),
        ),
    ):
        updated = await StudentAcademicService.update_academic_session(
            db=db,
            tenant_id=tenant_id,
            academic_session_id=session.id,
            payload=AcademicSessionUpdate(next_academic_session_id=next_session.id),
        )

    assert updated.next_academic_session_id == next_session.id


@pytest.mark.asyncio
async def test_update_open_academic_session_rejects_lifecycle_fields() -> None:
    tenant_id = uuid.uuid4()
    session = _session(tenant_id)
    session.status = AcademicSessionStatus.OPEN
    session.is_current = True
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_academic_session_by_id",
        new=AsyncMock(return_value=session),
    ):
        with pytest.raises(ConflictException):
            await StudentAcademicService.update_academic_session(
                db=db,
                tenant_id=tenant_id,
                academic_session_id=session.id,
                payload=AcademicSessionUpdate(name="2027/2028"),
            )
