from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.student_academics.models import AcademicTermStatus


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED])
async def test_term_specialization_is_immutable_once_closing_begins(status) -> None:
    db = AsyncMock()
    term = SimpleNamespace(id=uuid4(), status=status)

    with pytest.raises(ConflictException, match="after term closing begins"):
        await AcademicCurriculumService._ensure_term_configuration_mutable(
            db,
            tenant_id=uuid4(),
            term=term,
        )

    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_term_specialization_locks_after_results_exist() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid4()
    db.execute.return_value = result
    term = SimpleNamespace(id=uuid4(), status=AcademicTermStatus.OPEN)

    with pytest.raises(ConflictException, match="results already exist"):
        await AcademicCurriculumService._ensure_term_configuration_mutable(
            db,
            tenant_id=uuid4(),
            term=term,
        )


@pytest.mark.asyncio
async def test_draft_term_specialization_remains_configurable() -> None:
    db = AsyncMock()
    term = SimpleNamespace(id=uuid4(), status=AcademicTermStatus.DRAFT)

    await AcademicCurriculumService._ensure_term_configuration_mutable(
        db,
        tenant_id=uuid4(),
        term=term,
    )

    db.execute.assert_not_awaited()
