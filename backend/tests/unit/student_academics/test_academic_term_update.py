from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.student_academics.models import AcademicTerm, AcademicTermName
from app.modules.student_academics.schemas import AcademicTermUpdate
from app.modules.student_academics.service_impl import StudentAcademicService


def _academic_term(tenant_id: uuid.UUID) -> AcademicTerm:
    return AcademicTerm(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        academic_session_id=uuid.uuid4(),
        name=AcademicTermName.FIRST_TERM,
        start_date=date(2026, 1, 12),
        end_date=date(2026, 4, 10),
        is_current=True,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_update_academic_term_ignores_nulls_and_updates_explicit_values() -> None:
    tenant_id = uuid.uuid4()
    term = _academic_term(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service_impl.StudentAcademicRepository.get_term_by_id",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.student_academics.service_impl.StudentAcademicRepository.save_academic_term",
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
                is_current=None,
                is_active=False,
            ),
        )

    assert updated is term
    assert term.name == AcademicTermName.FIRST_TERM
    assert term.start_date == date(2026, 1, 12)
    assert term.end_date == date(2026, 4, 10)
    assert term.is_current is True
    assert term.is_active is False
    save_term.assert_awaited_once()
    db.commit.assert_awaited_once()
