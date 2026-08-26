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


@pytest.fixture(autouse=True)
def _allow_academic_writes():
    with patch(
        "app.modules.subjects.service.ensure_academic_write_window",
        new=AsyncMock(),
    ):
        yield


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
        archived_at=None,
        archived_by_admin_id=None,
        created_at=now,
        updated_at=now,
    )


def _usage_counts(**overrides: int) -> dict[str, int]:
    counts = {
        "curriculum_subjects_total": 0,
        "curriculum_subjects_live": 0,
        "teacher_links_total": 0,
        "teacher_links_live": 0,
        "teacher_assignments_total": 0,
        "teacher_assignments_live": 0,
        "results_total": 0,
        "results_live": 0,
        "report_card_lines_total": 0,
        "report_card_lines_live": 0,
    }
    counts.update(overrides)
    return counts


def test_update_subject_rejects_explicit_null_name() -> None:
    with pytest.raises(ValidationError):
        SubjectUpdate(name=None)


@pytest.mark.asyncio
async def test_used_subject_can_still_update_description() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    db = AsyncMock()
    dependency_mock = AsyncMock(return_value=_usage_counts(results_total=5))

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(side_effect=[subject, subject]),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_dependencies",
            new=dependency_mock,
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.update_subject",
            new=AsyncMock(return_value=subject),
        ),
    ):
        updated = await SubjectService.update_subject(
            db,
            _actor(tenant_id),
            subject.id,
            SubjectUpdate(description="  Advanced   numbers  "),
        )

    assert updated.description == "Advanced numbers"
    dependency_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_used_subject_cannot_change_semantic_name() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    counts = _usage_counts(curriculum_subjects_total=1)

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_dependencies",
            new=AsyncMock(return_value=counts),
        ),
    ):
        with pytest.raises(ConflictException, match="name and code are locked") as exc_info:
            await SubjectService.update_subject(
                AsyncMock(),
                _actor(tenant_id),
                subject.id,
                SubjectUpdate(name="Chemistry"),
            )

    assert exc_info.value.payload == {"dependency_counts": counts}


@pytest.mark.asyncio
async def test_used_subject_cannot_clear_code() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_dependencies",
            new=AsyncMock(return_value=_usage_counts(results_total=1)),
        ),
    ):
        with pytest.raises(ConflictException, match="name and code are locked"):
            await SubjectService.update_subject(
                AsyncMock(),
                _actor(tenant_id),
                subject.id,
                SubjectUpdate(code=None),
            )


@pytest.mark.asyncio
async def test_same_normalized_name_correction_is_allowed_after_usage() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    db = AsyncMock()
    dependency_mock = AsyncMock(return_value=_usage_counts(results_total=1))

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(side_effect=[subject, subject]),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_dependencies",
            new=dependency_mock,
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.update_subject",
            new=AsyncMock(return_value=subject),
        ),
    ):
        updated = await SubjectService.update_subject(
            db,
            _actor(tenant_id),
            subject.id,
            SubjectUpdate(name="  MATHEMATICS  "),
        )

    assert updated.name == "MATHEMATICS"
    assert updated.normalized_name == "mathematics"
    dependency_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_unused_subject_can_change_name_and_code() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(side_effect=[subject, subject]),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_dependencies",
            new=AsyncMock(return_value=_usage_counts()),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_normalized_name",
            new=AsyncMock(return_value=None),
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
            db,
            _actor(tenant_id),
            subject.id,
            SubjectUpdate(name="Further   Mathematics", code=" f mth "),
        )

    assert updated.name == "Further Mathematics"
    assert updated.normalized_name == "further mathematics"
    assert updated.code == "FMTH"
    assert updated.normalized_code == "FMTH"


@pytest.mark.asyncio
async def test_update_subject_rejects_archived_subject() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    subject.is_active = False
    subject.archived_at = datetime.now(timezone.utc)
    subject.archived_by_admin_id = uuid.uuid4()

    with patch(
        "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
        new=AsyncMock(return_value=subject),
    ):
        with pytest.raises(ConflictException, match="Archived subjects cannot be updated"):
            await SubjectService.update_subject(
                AsyncMock(),
                _actor(tenant_id),
                subject.id,
                SubjectUpdate(description="Changed"),
            )
