from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.student_academics.models import AcademicSession, AcademicSessionStatus
from app.modules.student_academics.progression_service import AcademicProgressionService


@pytest.mark.asyncio
async def test_first_term_is_enough_to_open_session_before_calendar_setup():
    tenant_id = uuid4()
    session = AcademicSession(
        id=uuid4(),
        tenant_id=tenant_id,
        name="2026/2027",
        start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31),
        status=AcademicSessionStatus.DRAFT,
        is_current=False,
    )
    actor = MagicMock()
    actor.id = uuid4()
    actor.tenant_id = tenant_id
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.progression_service.AcademicSessionLifecycleRepository.get_by_id",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "app.modules.student_academics.progression_service.StudentAcademicService._validate_session_dates",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.progression_service.StudentAcademicService.academic_session_dependency_preview",
            new=AsyncMock(return_value=SimpleNamespace(can_open=True)),
        ),
        patch(
            "app.modules.student_academics.progression_service.AcademicSessionLifecycleRepository.get_current_open",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.student_academics.progression_service.AcademicSessionLifecycleRepository.save",
            new=AsyncMock(side_effect=lambda _db, row: row),
        ),
        patch(
            "app.modules.student_academics.progression_service.StudentAcademicService._record_academic_lifecycle",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.progression_service.AcademicSessionResponse.model_validate",
            side_effect=lambda row: row,
        ),
    ):
        result = await AcademicProgressionService.open_session(
            db,
            actor=actor,
            session_id=session.id,
        )

    assert result.status == AcademicSessionStatus.OPEN
    assert result.is_current is True
    db.commit.assert_awaited_once()
