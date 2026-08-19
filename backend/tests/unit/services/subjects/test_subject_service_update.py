from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.exceptions import ConflictException
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


def test_update_subject_rejects_explicit_null_name() -> None:
    with pytest.raises(ValidationError):
        SubjectUpdate(name=None)


@pytest.mark.asyncio
async def test_update_subject_clears_explicit_nullable_values() -> None:
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
    assert updated.code is None
    assert updated.normalized_code is None
    assert updated.description is None


@pytest.mark.asyncio
async def test_update_subject_stores_code_canonically() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_normalized_code",
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
            subject_data=SubjectUpdate(code=" m th "),
        )

    assert updated.code == "MTH"
    assert updated.normalized_code == "MTH"


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


@pytest.mark.asyncio
async def test_update_subject_rejects_archived_subject() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    subject.is_active = False
    subject.archived_at = datetime.now(timezone.utc)
    subject.archived_by_admin_id = uuid.uuid4()
    db = AsyncMock()

    with patch(
        "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
        new=AsyncMock(return_value=subject),
    ):
        with pytest.raises(ConflictException):
            await SubjectService.update_subject(
                db=db,
                actor=_actor(tenant_id),
                subject_id=subject.id,
                subject_data=SubjectUpdate(name="Further Mathematics"),
            )


@pytest.mark.asyncio
async def test_delete_subject_with_dependencies_requires_archive() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_subject_dependencies",
            new=AsyncMock(
                return_value={
                    "class_subjects": 1,
                    "teacher_links": 0,
                    "teacher_assignments": 0,
                    "results": 0,
                    "report_card_lines": 0,
                }
            ),
        ),
    ):
        with pytest.raises(ConflictException):
            await SubjectService.delete_subject(
                db=db,
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )


@pytest.mark.asyncio
async def test_delete_subject_rejects_active_subject_before_dependency_check() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    db = AsyncMock()
    count_mock = AsyncMock(return_value={})

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_subject_dependencies",
            new=count_mock,
        ),
    ):
        with pytest.raises(ConflictException, match="Active subjects cannot be deleted"):
            await SubjectService.delete_subject(
                db=db,
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )

    count_mock.assert_not_awaited()
