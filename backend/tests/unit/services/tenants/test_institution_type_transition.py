from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.classes.models import AcademicLevelStatus
from app.tenant_management.institution_transition import (
    RESET_CONFIRMATION,
    InstitutionTypeTransitionMode,
    InstitutionTypeTransitionPreview,
    InstitutionTypeTransitionRequest,
    InstitutionTypeTransitionService,
)
from app.tenant_management.models import InstitutionType


def _scalar_result(items):
    result = MagicMock()
    result.scalars.return_value = items
    return result


def _tenant(institution_type=InstitutionType.PRIMARY_SCHOOL):
    return SimpleNamespace(id=uuid4(), institution_type=institution_type)


@pytest.mark.asyncio
async def test_transition_is_direct_before_institution_specific_setup_exists():
    tenant = _tenant()
    db = AsyncMock()
    db.execute.side_effect = [_scalar_result([]), _scalar_result([])]

    with patch.object(
        InstitutionTypeTransitionService,
        "_count",
        new=AsyncMock(side_effect=[0, 0, 0, 0]),
    ):
        preview = await InstitutionTypeTransitionService._inspect(
            db,
            tenant=tenant,
            requested_type=InstitutionType.SECONDARY_SCHOOL,
            lock=False,
        )

    assert preview.mode == InstitutionTypeTransitionMode.DIRECT
    assert preview.reset_counts == {"academic_levels": 0, "departments": 0}
    assert preview.blocker_counts == {}


@pytest.mark.asyncio
async def test_disposable_draft_structure_requires_explicit_reset_confirmation():
    tenant = _tenant()
    level = SimpleNamespace(status=AcademicLevelStatus.DRAFT)
    department = SimpleNamespace()
    db = AsyncMock()
    db.execute.side_effect = [_scalar_result([level]), _scalar_result([department])]

    with patch.object(
        InstitutionTypeTransitionService,
        "_count",
        new=AsyncMock(side_effect=[0, 0, 0, 0]),
    ):
        preview = await InstitutionTypeTransitionService._inspect(
            db,
            tenant=tenant,
            requested_type=InstitutionType.SECONDARY_SCHOOL,
            lock=False,
        )

    assert preview.mode == InstitutionTypeTransitionMode.RESET_REQUIRED
    assert preview.confirmation_text == RESET_CONFIRMATION
    assert preview.reset_counts == {"academic_levels": 1, "departments": 1}


@pytest.mark.asyncio
async def test_published_level_blocks_institution_type_transition():
    tenant = _tenant()
    level = SimpleNamespace(status=AcademicLevelStatus.ACTIVE)
    db = AsyncMock()
    db.execute.side_effect = [_scalar_result([level]), _scalar_result([])]

    with patch.object(
        InstitutionTypeTransitionService,
        "_count",
        new=AsyncMock(side_effect=[0, 0, 0, 0]),
    ):
        preview = await InstitutionTypeTransitionService._inspect(
            db,
            tenant=tenant,
            requested_type=InstitutionType.SECONDARY_SCHOOL,
            lock=False,
        )

    assert preview.mode == InstitutionTypeTransitionMode.BLOCKED
    assert preview.blocker_counts["published_levels"] == 1


@pytest.mark.asyncio
async def test_historical_student_enrollment_blocks_transition_even_with_draft_level():
    tenant = _tenant()
    level = SimpleNamespace(status=AcademicLevelStatus.DRAFT)
    db = AsyncMock()
    db.execute.side_effect = [_scalar_result([level]), _scalar_result([])]

    with patch.object(
        InstitutionTypeTransitionService,
        "_count",
        new=AsyncMock(side_effect=[0, 0, 0, 1]),
    ):
        preview = await InstitutionTypeTransitionService._inspect(
            db,
            tenant=tenant,
            requested_type=InstitutionType.SECONDARY_SCHOOL,
            lock=False,
        )

    assert preview.mode == InstitutionTypeTransitionMode.BLOCKED
    assert preview.blocker_counts["student_enrollments"] == 1


@pytest.mark.asyncio
async def test_apply_rechecks_and_rejects_reset_without_typed_confirmation():
    tenant = _tenant()
    db = AsyncMock()
    preview = InstitutionTypeTransitionPreview(
        current_type=InstitutionType.PRIMARY_SCHOOL,
        requested_type=InstitutionType.SECONDARY_SCHOOL,
        mode=InstitutionTypeTransitionMode.RESET_REQUIRED,
        reset_counts={"academic_levels": 1, "departments": 0},
        blocker_counts={},
        blocker_messages=[],
        confirmation_text=RESET_CONFIRMATION,
    )

    with (
        patch(
            "app.tenant_management.institution_transition.TenantRepository.get_by_id",
            new=AsyncMock(return_value=tenant),
        ),
        patch.object(
            InstitutionTypeTransitionService,
            "_inspect",
            new=AsyncMock(return_value=preview),
        ),
    ):
        with pytest.raises(ConflictException):
            await InstitutionTypeTransitionService.apply(
                db,
                tenant_id=tenant.id,
                payload=InstitutionTypeTransitionRequest(
                    institution_type=InstitutionType.SECONDARY_SCHOOL,
                ),
            )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
