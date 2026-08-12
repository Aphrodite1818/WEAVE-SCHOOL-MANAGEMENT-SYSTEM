from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.modules.classes.models import (
    AcademicLevelProgressionMode,
    ProgressionSelectionTargetType,
)
from app.modules.classes.schemas import AcademicLevelProgressionConfigureRequest
from app.modules.classes.service import AcademicLevelService
from app.core.exceptions import BadRequestException


def test_direct_requires_next_level() -> None:
    with pytest.raises(ValidationError):
        AcademicLevelProgressionConfigureRequest(
            progression_mode=AcademicLevelProgressionMode.DIRECT
        )


def test_direct_rejects_student_selection_options() -> None:
    with pytest.raises(ValidationError):
        AcademicLevelProgressionConfigureRequest(
            progression_mode=AcademicLevelProgressionMode.DIRECT,
            next_level_id=uuid4(),
            target_level_ids=[uuid4()],
        )


def test_student_selection_requires_target_type_and_options() -> None:
    with pytest.raises(ValidationError):
        AcademicLevelProgressionConfigureRequest(
            progression_mode=AcademicLevelProgressionMode.STUDENT_SELECTION
        )


def test_level_selection_accepts_only_level_destinations() -> None:
    target = uuid4()
    payload = AcademicLevelProgressionConfigureRequest(
        progression_mode=AcademicLevelProgressionMode.STUDENT_SELECTION,
        selection_target_type=ProgressionSelectionTargetType.LEVEL,
        target_level_ids=[target],
    )
    assert payload.target_level_ids == [target]
    with pytest.raises(ValidationError):
        AcademicLevelProgressionConfigureRequest(
            progression_mode=AcademicLevelProgressionMode.STUDENT_SELECTION,
            selection_target_type=ProgressionSelectionTargetType.LEVEL,
            target_level_ids=[target],
            target_classroom_ids=[uuid4()],
        )


def test_classroom_selection_accepts_only_classroom_destinations() -> None:
    target = uuid4()
    payload = AcademicLevelProgressionConfigureRequest(
        progression_mode=AcademicLevelProgressionMode.STUDENT_SELECTION,
        selection_target_type=ProgressionSelectionTargetType.CLASSROOM,
        target_classroom_ids=[target],
    )
    assert payload.target_classroom_ids == [target]


def test_student_selection_rejects_duplicate_destinations() -> None:
    target = uuid4()
    with pytest.raises(ValidationError):
        AcademicLevelProgressionConfigureRequest(
            progression_mode=AcademicLevelProgressionMode.STUDENT_SELECTION,
            selection_target_type=ProgressionSelectionTargetType.LEVEL,
            target_level_ids=[target, target],
        )


def test_terminal_rejects_all_destinations() -> None:
    payload = AcademicLevelProgressionConfigureRequest(
        progression_mode=AcademicLevelProgressionMode.TERMINAL
    )
    assert payload.next_level_id is None
    with pytest.raises(ValidationError):
        AcademicLevelProgressionConfigureRequest(
            progression_mode=AcademicLevelProgressionMode.TERMINAL,
            next_level_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_selection_edges_cannot_create_indirect_cycle(monkeypatch) -> None:
    source_id = uuid4()
    target_id = uuid4()
    monkeypatch.setattr(
        "app.modules.classes.service.AcademicLevelRepository.list_for_tenant",
        AsyncMock(
            return_value=[
                SimpleNamespace(id=source_id, next_level_id=None),
                SimpleNamespace(id=target_id, next_level_id=None),
            ]
        ),
    )
    monkeypatch.setattr(
        "app.modules.classes.service.AcademicLevelRepository.list_progression_edges",
        AsyncMock(return_value=[(target_id, source_id)]),
    )

    with pytest.raises(BadRequestException):
        await AcademicLevelService._ensure_progression_remains_acyclic(
            AsyncMock(),
            tenant_id=uuid4(),
            source_level_id=source_id,
            proposed_target_level_ids={target_id},
        )
