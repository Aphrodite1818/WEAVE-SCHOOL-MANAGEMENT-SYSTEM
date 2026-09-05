from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics.curriculum_bulk_service import add_curriculum_subjects
from app.modules.student_academics.curriculum_v2_schemas import CurriculumSubjectsBulkCreate

SERVICE = "app.modules.student_academics.curriculum_bulk_service"


def batch():
    return CurriculumSubjectsBulkCreate(
        subjects=[
            {"subject_id": uuid4()},
            {
                "subject_id": uuid4(),
                "is_elective": True,
                "academic_level_department_ids": [uuid4(), uuid4()],
            },
        ]
    )


def database(payload, *, missing=False, duplicate=False):
    subjects = MagicMock()
    subjects.scalars.return_value = [
        SimpleNamespace(id=row.subject_id) for row in payload.subjects
    ][int(missing) :]
    existing = MagicMock()
    existing.first.return_value = (uuid4(),) if duplicate else None
    return SimpleNamespace(
        execute=AsyncMock(side_effect=[subjects, existing]),
        add=MagicMock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_bulk_add_commits_once_and_preserves_multiple_department_scopes():
    payload = batch()
    db = database(payload)
    tenant_id, level_id = uuid4(), uuid4()
    curriculum = SimpleNamespace(id=uuid4(), academic_level_id=level_id)
    with (
        patch(f"{SERVICE}.ensure_academic_write_window", new=AsyncMock()),
        patch(
            f"{SERVICE}.AcademicCurriculumService._curriculum",
            new=AsyncMock(return_value=curriculum),
        ) as load,
        patch(
            f"{SERVICE}.AcademicCurriculumService._validated_level_department_ids", new=AsyncMock()
        ) as validate,
    ):
        result = await add_curriculum_subjects(db, tenant_id, level_id, payload)
    assert result == {"created": 2}
    load.assert_awaited_once_with(db, tenant_id, level_id, require_active_level=True)
    validate.assert_awaited_once_with(
        db,
        tenant_id=tenant_id,
        academic_level_id=level_id,
        ids=payload.subjects[1].academic_level_department_ids,
    )
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()
    added = [call.args[0] for call in db.add.call_args_list]
    assert len(added) == 4  # Two memberships and both selected scopes.
    assert all(row.tenant_id == tenant_id for row in added)
    for call in db.execute.call_args_list:
        assert tenant_id in call.args[0].compile().params.values()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["missing_subject", "duplicate", "wrong_level_department", "inactive_level", "integrity"],
)
async def test_bulk_failure_rolls_back_without_partial_commit(failure):
    payload = batch()
    db = database(payload, missing=failure == "missing_subject", duplicate=failure == "duplicate")
    if failure == "integrity":
        db.flush.side_effect = [None, IntegrityError("insert", {}, Exception("conflict"))]
    with (
        patch(f"{SERVICE}.ensure_academic_write_window", new=AsyncMock()),
        patch(
            f"{SERVICE}.AcademicCurriculumService._curriculum",
            new=AsyncMock(
                return_value=SimpleNamespace(id=uuid4()),
                side_effect=ConflictException("Inactive level")
                if failure == "inactive_level"
                else None,
            ),
        ),
        patch(
            f"{SERVICE}.AcademicCurriculumService._validated_level_department_ids",
            new=AsyncMock(
                side_effect=ConflictException("Wrong level or tenant")
                if failure == "wrong_level_department"
                else None
            ),
        ),
    ):
        with pytest.raises((ConflictException, NotFoundException)):
            await add_curriculum_subjects(db, uuid4(), uuid4(), payload)
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
    if failure != "integrity":
        db.add.assert_not_called()


@pytest.mark.parametrize(
    "subjects",
    [
        [],
        [{"subject_id": "invalid"}],
        [{"subject_id": str(uuid4()), "academic_level_department_ids": ["invalid"]}],
    ],
)
def test_bulk_payload_rejects_invalid_input(subjects):
    with pytest.raises(ValidationError):
        CurriculumSubjectsBulkCreate(subjects=subjects)


def test_bulk_payload_rejects_duplicate_membership():
    subject_id = uuid4()
    with pytest.raises(ValidationError, match="unique"):
        CurriculumSubjectsBulkCreate(
            subjects=[{"subject_id": subject_id}, {"subject_id": subject_id}]
        )
