from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.subjects.models import Subject
from app.modules.subjects.schemas import SubjectUpdate
from app.modules.subjects.service import SubjectService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def _actor(tenant_id: uuid.UUID) -> TenantAdmin:
    return TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.test",
        password_hash="hashed",
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )


def _subject(tenant_id: uuid.UUID) -> Subject:
    now = datetime.now(timezone.utc)
    return Subject(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Mathematics",
        normalized_name="mathematics",
        code="MTH",
        normalized_code="MTH",
        description="Numbers and reasoning",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_subject_ignores_explicit_null_values() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_normalized_name",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.update_subject",
            new=AsyncMock(return_value=subject),
        ),
    ):
        updated = await SubjectService.update_subject(
            db=db,
            actor=_actor(tenant_id),
            subject_id=subject.id,
            subject_data=SubjectUpdate(
                name="Mathematics Advanced",
                code=None,
                description=None,
            ),
        )

    assert updated.name == "Mathematics Advanced"
    assert updated.code == "MTH"
    assert updated.description == "Numbers and reasoning"


@pytest.mark.asyncio
async def test_update_subject_applies_explicit_values() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_normalized_name",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.update_subject",
            new=AsyncMock(return_value=subject),
        ),
    ):
        updated = await SubjectService.update_subject(
            db=db,
            actor=_actor(tenant_id),
            subject_id=subject.id,
            subject_data=SubjectUpdate(name="Further Mathematics"),
        )

    assert updated.name == "Further Mathematics"
    assert updated.normalized_name == "further mathematics"
