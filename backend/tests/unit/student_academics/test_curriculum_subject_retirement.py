from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.curriculum_v2_schemas import CurriculumSubjectUpdate
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService


def _scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalar_one(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


@pytest.mark.asyncio
async def test_curriculum_subject_can_be_retired_without_rewriting_history() -> None:
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        curriculum_id=uuid4(),
        subject_id=uuid4(),
        is_elective=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    subject = SimpleNamespace(name="Physics", code="PHY")
    db = AsyncMock()
    db.execute.side_effect = [
        _scalar_one_or_none(row),
        _scalar_one(subject),
    ]

    response = await AcademicCurriculumService.update_subject(
        db=db,
        tenant_id=tenant_id,
        curriculum_subject_id=row.id,
        payload=CurriculumSubjectUpdate(is_active=False),
    )

    assert row.is_active is False
    assert response.is_active is False
    # No StudentSubjectResult lookup is needed for a lifecycle-only change.
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_curriculum_subject_elective_meaning_stays_locked_after_results_exist() -> None:
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        curriculum_id=uuid4(),
        subject_id=uuid4(),
        is_elective=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db = AsyncMock()
    db.execute.side_effect = [
        _scalar_one_or_none(row),
        _scalar_one_or_none(uuid4()),
    ]

    with pytest.raises(ConflictException, match="elective setting cannot change"):
        await AcademicCurriculumService.update_subject(
            db=db,
            tenant_id=tenant_id,
            curriculum_subject_id=row.id,
            payload=CurriculumSubjectUpdate(is_elective=True),
        )

    assert row.is_elective is False
    db.commit.assert_not_awaited()
