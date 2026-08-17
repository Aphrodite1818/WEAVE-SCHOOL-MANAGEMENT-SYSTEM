from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.classes.models import AcademicCategory
from app.modules.classes.repository import AcademicLevelRepository
from app.modules.student_academics.progression_service import AcademicProgressionService
from app.tenant_management.models import InstitutionType
from app.tenant_management.repository import TenantRepository


def level(category: AcademicCategory, position: int, *, name: str = "Unparsed name"):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        category=category,
        position=position,
    )


@pytest.mark.asyncio
async def test_progression_uses_next_position_then_immediate_next_category(monkeypatch) -> None:
    tenant_id = uuid4()
    current = level(AcademicCategory.JUNIOR_SECONDARY, 10, name="Final-looking name")
    next_same = level(AcademicCategory.JUNIOR_SECONDARY, 20, name="Completely custom")
    first_senior = level(AcademicCategory.SENIOR_SECONDARY, 30, name="Not SS1")
    monkeypatch.setattr(
        TenantRepository,
        "get_by_id",
        AsyncMock(return_value=SimpleNamespace(institution_type=InstitutionType.SECONDARY_SCHOOL)),
    )
    list_levels = AsyncMock(return_value=[first_senior, next_same, current])
    monkeypatch.setattr(AcademicLevelRepository, "list_for_tenant", list_levels)

    resolved = await AcademicProgressionService.resolve_next_level(
        AsyncMock(), tenant_id=tenant_id, current_level=current
    )
    assert resolved is next_same

    resolved = await AcademicProgressionService.resolve_next_level(
        AsyncMock(), tenant_id=tenant_id, current_level=next_same
    )
    assert resolved is first_senior
    TenantRepository.get_by_id.assert_awaited_with(ANY, tenant_id)
    assert list_levels.await_count == 2


@pytest.mark.asyncio
async def test_final_level_of_final_category_is_terminal(monkeypatch) -> None:
    tenant_id = uuid4()
    current = level(AcademicCategory.SENIOR_SECONDARY, 3)
    monkeypatch.setattr(
        TenantRepository,
        "get_by_id",
        AsyncMock(return_value=SimpleNamespace(institution_type=InstitutionType.SECONDARY_SCHOOL)),
    )
    monkeypatch.setattr(
        AcademicLevelRepository,
        "list_for_tenant",
        AsyncMock(return_value=[current]),
    )

    assert (
        await AcademicProgressionService.resolve_next_level(
            AsyncMock(), tenant_id=tenant_id, current_level=current
        )
        is None
    )


@pytest.mark.asyncio
async def test_missing_next_category_blocks_instead_of_graduating(monkeypatch) -> None:
    tenant_id = uuid4()
    final_junior = level(AcademicCategory.JUNIOR_SECONDARY, 30, name="Foundation C")
    monkeypatch.setattr(
        TenantRepository,
        "get_by_id",
        AsyncMock(return_value=SimpleNamespace(institution_type=InstitutionType.SECONDARY_SCHOOL)),
    )
    monkeypatch.setattr(
        AcademicLevelRepository,
        "list_for_tenant",
        AsyncMock(return_value=[final_junior]),
    )

    with pytest.raises(ConflictException, match="Senior Secondary"):
        await AcademicProgressionService.resolve_next_level(
            AsyncMock(), tenant_id=tenant_id, current_level=final_junior
        )


@pytest.mark.asyncio
async def test_primary_progression_does_not_skip_an_unconfigured_category(monkeypatch) -> None:
    tenant_id = uuid4()
    final_kindergarten = level(AcademicCategory.KINDERGARTEN, 2, name="KG Two")
    primary_one = level(AcademicCategory.PRIMARY, 1, name="Primary One")
    monkeypatch.setattr(
        TenantRepository,
        "get_by_id",
        AsyncMock(return_value=SimpleNamespace(institution_type=InstitutionType.PRIMARY_SCHOOL)),
    )
    monkeypatch.setattr(
        AcademicLevelRepository,
        "list_for_tenant",
        AsyncMock(return_value=[final_kindergarten, primary_one]),
    )

    with pytest.raises(ConflictException, match="Nursery"):
        await AcademicProgressionService.resolve_next_level(
            AsyncMock(), tenant_id=tenant_id, current_level=final_kindergarten
        )
