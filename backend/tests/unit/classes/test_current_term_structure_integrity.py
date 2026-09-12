from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import AcademicTermName
from app.modules.classes.current_term_integrity import (
    CurrentTermDepartmentRequirement,
    CurrentTermStructureIntegrity,
)


def _level(*, threshold: int | None = 1):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="SS1",
        specialization_required_from_term_position=threshold,
    )


def _term(name=AcademicTermName.FIRST_TERM):
    return SimpleNamespace(id=uuid.uuid4(), name=name)


def _link(level_id: uuid.UUID):
    return SimpleNamespace(
        id=uuid.uuid4(),
        academic_level_id=level_id,
        is_active=True,
        archived_at=None,
        department=SimpleNamespace(is_active=True, archived_at=None),
    )


@pytest.mark.asyncio
async def test_no_current_term_requires_no_department() -> None:
    level = _level()
    with patch.object(
        CurrentTermStructureIntegrity,
        "current_open_term",
        new=AsyncMock(return_value=None),
    ):
        requirement = await CurrentTermStructureIntegrity.requirement_for_active_class(
            AsyncMock(),
            tenant_id=uuid.uuid4(),
            level=level,
        )

    assert requirement is None


@pytest.mark.asyncio
async def test_future_specialization_term_requires_no_department_yet() -> None:
    level = _level(threshold=2)
    term = _term(AcademicTermName.FIRST_TERM)
    with patch.object(
        CurrentTermStructureIntegrity,
        "current_open_term",
        new=AsyncMock(return_value=term),
    ):
        requirement = await CurrentTermStructureIntegrity.requirement_for_active_class(
            AsyncMock(),
            tenant_id=uuid.uuid4(),
            level=level,
        )

    assert requirement is None


@pytest.mark.asyncio
async def test_current_specialization_blocks_when_level_has_no_departments() -> None:
    tenant_id = uuid.uuid4()
    level = _level(threshold=1)
    term = _term()
    with (
        patch.object(
            CurrentTermStructureIntegrity,
            "current_open_term",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.classes.current_term_integrity.AcademicLevelDepartmentRepository.list_for_level",
            new=AsyncMock(return_value=[]),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await CurrentTermStructureIntegrity.requirement_for_active_class(
                AsyncMock(),
                tenant_id=tenant_id,
                level=level,
            )

    assert exc_info.value.payload["code"] == "CURRENT_TERM_SPECIALIZATION_DEPARTMENTS_REQUIRED"
    assert exc_info.value.payload["departments_available"] == 0


@pytest.mark.asyncio
async def test_current_specialization_requires_department_selection_for_new_class() -> None:
    tenant_id = uuid.uuid4()
    level = _level(threshold=1)
    term = _term()
    link = _link(level.id)
    with (
        patch.object(
            CurrentTermStructureIntegrity,
            "current_open_term",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.classes.current_term_integrity.AcademicLevelDepartmentRepository.list_for_level",
            new=AsyncMock(return_value=[link]),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await CurrentTermStructureIntegrity.requirement_for_active_class(
                AsyncMock(),
                tenant_id=tenant_id,
                level=level,
            )

    assert exc_info.value.payload["code"] == "CURRENT_TERM_SPECIALIZATION_SELECTION_REQUIRED"
    assert exc_info.value.payload["departments_available"] == 1


@pytest.mark.asyncio
async def test_valid_department_returns_atomic_assignment_requirement() -> None:
    tenant_id = uuid.uuid4()
    level = _level(threshold=1)
    term = _term()
    link = _link(level.id)
    with (
        patch.object(
            CurrentTermStructureIntegrity,
            "current_open_term",
            new=AsyncMock(return_value=term),
        ),
        patch(
            "app.modules.classes.current_term_integrity.AcademicLevelDepartmentRepository.list_for_level",
            new=AsyncMock(return_value=[link]),
        ),
        patch.object(
            CurrentTermStructureIntegrity,
            "_validated_requested_department",
            new=AsyncMock(return_value=link),
        ),
    ):
        requirement = await CurrentTermStructureIntegrity.requirement_for_active_class(
            AsyncMock(),
            tenant_id=tenant_id,
            level=level,
            requested_department_link_id=link.id,
        )

    assert requirement == CurrentTermDepartmentRequirement(
        term=term,
        department_link=link,
        assignment_exists=False,
    )


def test_add_assignment_queues_current_term_specialization_in_same_transaction() -> None:
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    level = _level()
    term = _term()
    link = _link(level.id)
    db = MagicMock()

    CurrentTermStructureIntegrity.add_assignment(
        db,
        tenant_id=tenant_id,
        class_id=class_id,
        admin_id=admin_id,
        requirement=CurrentTermDepartmentRequirement(
            term=term,
            department_link=link,
            assignment_exists=False,
        ),
    )

    row = db.add.call_args.args[0]
    assert row.tenant_id == tenant_id
    assert row.class_id == class_id
    assert row.academic_term_id == term.id
    assert row.academic_level_department_id == link.id
    assert row.assigned_by_admin_id == admin_id
