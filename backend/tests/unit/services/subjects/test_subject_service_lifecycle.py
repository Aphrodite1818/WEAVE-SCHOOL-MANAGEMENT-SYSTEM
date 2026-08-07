from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestException, ConflictException
from app.modules.subjects.models import Subject
from app.modules.subjects.schemas import SubjectCreate
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


def _subject(tenant_id: uuid.UUID, *, active: bool = True) -> Subject:
    now = datetime.now(timezone.utc)
    return Subject(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Mathematics",
        normalized_name="mathematics",
        code="MTH",
        normalized_code="MTH",
        description="Numbers and reasoning",
        is_active=active,
        archived_at=None,
        archived_by_admin_id=None,
        created_at=now,
        updated_at=now,
    )


def _no_live_dependencies() -> dict[str, int]:
    return {
        "active_class_subjects": 0,
        "active_teacher_links": 0,
        "active_teacher_assignments": 0,
    }


@pytest.mark.asyncio
async def test_create_subject_defaults_active_and_canonicalizes_code() -> None:
    tenant_id = uuid.uuid4()
    db = AsyncMock()
    created = _subject(tenant_id)

    async def create_subject(*, db, subject):
        subject.id = created.id
        subject.created_at = created.created_at
        subject.updated_at = created.updated_at
        return subject

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_normalized_name",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_normalized_code",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.create_subject",
            new=AsyncMock(side_effect=create_subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=created),
        ),
    ):
        subject = await SubjectService.create_subject(
            db=db,
            actor=_actor(tenant_id),
            subject_data=SubjectCreate(
                name="Mathematics",
                code=" m th ",
                description="Numbers",
            ),
        )

    assert subject.is_active is True
    assert subject.code == "MTH"
    assert subject.normalized_code == "MTH"


@pytest.mark.asyncio
async def test_create_subject_rejects_duplicate_normalized_name() -> None:
    tenant_id = uuid.uuid4()

    with patch(
        "app.modules.subjects.service.SubjectRepository.get_subject_by_normalized_name",
        new=AsyncMock(return_value=_subject(tenant_id)),
    ):
        with pytest.raises(BadRequestException, match="name already exists"):
            await SubjectService.create_subject(
                db=AsyncMock(),
                actor=_actor(tenant_id),
                subject_data=SubjectCreate(name=" Mathematics "),
            )


@pytest.mark.asyncio
async def test_create_subject_rejects_duplicate_normalized_code() -> None:
    tenant_id = uuid.uuid4()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_normalized_name",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_normalized_code",
            new=AsyncMock(return_value=_subject(tenant_id)),
        ),
    ):
        with pytest.raises(BadRequestException, match="code already exists"):
            await SubjectService.create_subject(
                db=AsyncMock(),
                actor=_actor(tenant_id),
                subject_data=SubjectCreate(name="Mathematics", code=" m th "),
            )


@pytest.mark.asyncio
async def test_active_subject_cannot_be_archived() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=True)

    with patch(
        "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
        new=AsyncMock(return_value=subject),
    ):
        with pytest.raises(
            ConflictException, match="Active subjects cannot be archived"
        ):
            await SubjectService.archive_subject(
                db=AsyncMock(),
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("counts", "message"),
    [
        (
            {
                "active_class_subjects": 1,
                "active_teacher_links": 0,
                "active_teacher_assignments": 0,
            },
            "actively offered",
        ),
        (
            {
                "active_class_subjects": 0,
                "active_teacher_links": 1,
                "active_teacher_assignments": 0,
            },
            "active teacher capability links",
        ),
        (
            {
                "active_class_subjects": 0,
                "active_teacher_links": 0,
                "active_teacher_assignments": 1,
            },
            "active teacher assignments",
        ),
    ],
)
async def test_deactivate_subject_blocks_live_dependencies(
    counts: dict[str, int],
    message: str,
) -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=True)

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_live_subject_dependencies",
            new=AsyncMock(return_value=counts),
        ),
    ):
        with pytest.raises(ConflictException, match=message):
            await SubjectService.deactivate_subject(
                db=AsyncMock(),
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )


@pytest.mark.asyncio
async def test_inactive_dependency_free_subject_can_be_archived() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_live_subject_dependencies",
            new=AsyncMock(return_value=_no_live_dependencies()),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.update_subject",
            new=AsyncMock(return_value=subject),
        ),
    ):
        archived = await SubjectService.archive_subject(
            db=db,
            actor=_actor(tenant_id),
            subject_id=subject.id,
        )

    assert archived.is_active is False
    assert archived.archived_at is not None
    assert archived.archived_by_admin_id is not None


@pytest.mark.asyncio
async def test_restore_returns_subject_to_inactive() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    subject.archived_at = datetime.now(timezone.utc)
    subject.archived_by_admin_id = uuid.uuid4()
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.update_subject",
            new=AsyncMock(return_value=subject),
        ),
    ):
        restored = await SubjectService.restore_subject(
            db=db,
            actor=_actor(tenant_id),
            subject_id=subject.id,
        )

    assert restored.is_active is False
    assert restored.archived_at is None
    assert restored.archived_by_admin_id is None


@pytest.mark.asyncio
async def test_archived_subject_cannot_activate_directly() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    subject.archived_at = datetime.now(timezone.utc)

    with patch(
        "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
        new=AsyncMock(return_value=subject),
    ):
        with pytest.raises(ConflictException, match="restored before activation"):
            await SubjectService.activate_subject(
                db=AsyncMock(),
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )


@pytest.mark.asyncio
async def test_delete_subject_returns_dependency_details_when_blocked() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    counts = {
        "class_subjects": 1,
        "teacher_links": 0,
        "teacher_assignments": 0,
        "results": 2,
        "report_card_lines": 0,
    }

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_subject_dependencies",
            new=AsyncMock(return_value=counts),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await SubjectService.delete_subject(
                db=AsyncMock(),
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )

    assert exc_info.value.payload["dependency_counts"] == counts


@pytest.mark.asyncio
async def test_subject_cannot_be_deleted_while_inactive_mapping_still_exists() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    counts = {
        "class_subjects": 1,
        "teacher_links": 0,
        "teacher_assignments": 0,
        "results": 0,
        "report_card_lines": 0,
    }

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_subject_dependencies",
            new=AsyncMock(return_value=counts),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await SubjectService.delete_subject(
                db=AsyncMock(),
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )

    assert exc_info.value.payload["dependency_counts"]["class_subjects"] == 1


@pytest.mark.asyncio
async def test_subject_can_be_deleted_after_final_unused_mapping_is_hard_deleted() -> (
    None
):
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    db = AsyncMock()
    delete_subject = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_subject_dependencies",
            new=AsyncMock(
                return_value={
                    "class_subjects": 0,
                    "teacher_links": 0,
                    "teacher_assignments": 0,
                    "results": 0,
                    "report_card_lines": 0,
                }
            ),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.delete_subject",
            new=delete_subject,
        ),
    ):
        await SubjectService.delete_subject(
            db=db,
            actor=_actor(tenant_id),
            subject_id=subject.id,
        )

    delete_subject.assert_awaited_once_with(db=db, subject=subject)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_subject_remains_blocked_until_every_class_mapping_is_deleted() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    db = AsyncMock()
    dependency_counts = AsyncMock(
        side_effect=[
            {
                "class_subjects": 1,
                "teacher_links": 0,
                "teacher_assignments": 0,
                "results": 0,
                "report_card_lines": 0,
            },
            {
                "class_subjects": 0,
                "teacher_links": 0,
                "teacher_assignments": 0,
                "results": 0,
                "report_card_lines": 0,
            },
        ]
    )
    delete_subject = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_subject_dependencies",
            new=dependency_counts,
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.delete_subject",
            new=delete_subject,
        ),
    ):
        with pytest.raises(ConflictException):
            await SubjectService.delete_subject(
                db=db,
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )

        await SubjectService.delete_subject(
            db=db,
            actor=_actor(tenant_id),
            subject_id=subject.id,
        )

    assert dependency_counts.await_count == 2
    delete_subject.assert_awaited_once_with(db=db, subject=subject)


@pytest.mark.asyncio
async def test_subject_delete_stays_blocked_when_mapping_history_prevents_mapping_delete() -> (
    None
):
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    counts = {
        "class_subjects": 1,
        "teacher_links": 0,
        "teacher_assignments": 1,
        "results": 0,
        "report_card_lines": 0,
    }

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_subject_dependencies",
            new=AsyncMock(return_value=counts),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await SubjectService.delete_subject(
                db=AsyncMock(),
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )

    assert exc_info.value.payload["dependency_counts"] == counts
