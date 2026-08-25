"""Database regression tests for level-owned departments."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.classes.models import (
    AcademicCategory,
    AcademicLevel,
    AcademicLevelStatus,
    Department,
)
from app.tenant_management.models import Tenant


@pytest.mark.asyncio
async def test_same_department_name_is_allowed_on_different_levels(
    db_session: AsyncSession,
    tenant: Tenant,
) -> None:
    first_level = AcademicLevel(
        tenant_id=tenant.id,
        name="SS1",
        normalized_name="ss1",
        category=AcademicCategory.SENIOR_SECONDARY,
        position=1,
        status=AcademicLevelStatus.ACTIVE,
    )
    second_level = AcademicLevel(
        tenant_id=tenant.id,
        name="SS2",
        normalized_name="ss2",
        category=AcademicCategory.SENIOR_SECONDARY,
        position=2,
        status=AcademicLevelStatus.ACTIVE,
    )
    db_session.add_all([first_level, second_level])
    await db_session.flush()

    db_session.add_all(
        [
            Department(
                tenant_id=tenant.id,
                academic_level_id=first_level.id,
                name="Science",
                normalized_name="science",
                is_active=True,
            ),
            Department(
                tenant_id=tenant.id,
                academic_level_id=second_level.id,
                name="Science",
                normalized_name="science",
                is_active=True,
            ),
        ]
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_same_department_name_is_rejected_twice_on_same_level(
    db_session: AsyncSession,
    tenant: Tenant,
) -> None:
    level = AcademicLevel(
        tenant_id=tenant.id,
        name="SS1",
        normalized_name="ss1",
        category=AcademicCategory.SENIOR_SECONDARY,
        position=1,
        status=AcademicLevelStatus.ACTIVE,
    )
    db_session.add(level)
    await db_session.flush()

    db_session.add(
        Department(
            tenant_id=tenant.id,
            academic_level_id=level.id,
            name="Science",
            normalized_name="science",
            is_active=True,
        )
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                Department(
                    tenant_id=tenant.id,
                    academic_level_id=level.id,
                    name="SCIENCE",
                    normalized_name="science",
                    is_active=True,
                )
            )
            await db_session.flush()
