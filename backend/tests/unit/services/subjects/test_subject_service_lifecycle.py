from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import CheckConstraint

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics.curriculum_models import CurriculumSubject
from app.modules.subjects.models import Subject
from app.modules.subjects.repository import SubjectRepository
from app.modules.subjects.schemas import SubjectCreate
from app.modules.subjects.service import SubjectService
from app.modules.teachers.models import TeacherMembership, TeacherMembershipStatus
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


@pytest.fixture(autouse=True)
def _allow_academic_writes():
    with patch(
        "app.modules.subjects.service.ensure_academic_write_window",
        new=AsyncMock(),
    ) as guard:
        yield guard


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


def _teacher(tenant_id: uuid.UUID) -> TeacherMembership:
    return TeacherMembership(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        teacher_account_id=uuid.uuid4(),
        status=TeacherMembershipStatus.ACTIVE,
        joined_at=datetime.now(timezone.utc),
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


def _dependencies(**overrides: int) -> dict[str, int]:
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


def test_subject_model_archive_metadata_and_relationship_contracts() -> None:
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in Subject.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    archive_contract = constraints["ck_subjects_archive_metadata_consistency"]
    assert "archived_at IS NULL AND archived_by_admin_id IS NULL" in archive_contract
    assert "archived_at IS NOT NULL AND is_active = false" in archive_contract

    relationship = Subject.__mapper__.relationships["teacher_links"]
    assert "delete" not in relationship.cascade
    assert "delete-orphan" not in relationship.cascade
    assert relationship.passive_deletes is True


def test_curriculum_subject_restricts_subject_deletion() -> None:
    fk = next(iter(CurriculumSubject.__table__.columns.subject_id.foreign_keys))
    assert fk.ondelete == "RESTRICT"


@pytest.mark.asyncio
async def test_create_subject_defaults_active_and_canonicalizes_values() -> None:
    tenant_id = uuid.uuid4()
    db = AsyncMock()
    created = _subject(tenant_id)

    async def create_subject(*, db, subject):
        subject.id = created.id
        subject.created_at = created.created_at
        subject.updated_at = created.updated_at
        return subject

    create_mock = AsyncMock(side_effect=create_subject)
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
            new=create_mock,
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=created),
        ),
    ):
        await SubjectService.create_subject(
            db=db,
            actor=_actor(tenant_id),
            subject_data=SubjectCreate(
                name="Further     Mathematics",
                code=" m th ",
                description="  Numbers   and reasoning  ",
            ),
        )

    created_subject = create_mock.await_args.kwargs["subject"]
    assert created_subject.is_active is True
    assert created_subject.name == "Further Mathematics"
    assert created_subject.normalized_name == "further mathematics"
    assert created_subject.code == "MTH"
    assert created_subject.normalized_code == "MTH"
    assert created_subject.description == "Numbers and reasoning"


@pytest.mark.asyncio
async def test_live_dependencies_block_deactivation() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    counts = _dependencies(results_total=2, results_live=1)

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
        with pytest.raises(ConflictException, match="live academic dependencies") as exc_info:
            await SubjectService.deactivate_subject(
                db=AsyncMock(),
                actor=_actor(tenant_id),
                subject_id=subject.id,
            )

    assert exc_info.value.payload == {"dependency_counts": {"results_live": 1}}


@pytest.mark.asyncio
async def test_historical_dependencies_do_not_block_deactivation() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_dependencies",
            new=AsyncMock(return_value=_dependencies(results_total=4)),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.update_subject",
            new=AsyncMock(return_value=subject),
        ),
    ):
        result = await SubjectService.deactivate_subject(db, _actor(tenant_id), subject.id)

    assert result.is_active is False


@pytest.mark.asyncio
async def test_archive_requires_inactive_subject() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=True)

    with patch(
        "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
        new=AsyncMock(return_value=subject),
    ):
        with pytest.raises(ConflictException, match="Deactivate the subject"):
            await SubjectService.archive_subject(AsyncMock(), _actor(tenant_id), subject.id)


@pytest.mark.asyncio
async def test_historical_usage_can_be_archived_and_records_actor() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    admin = _actor(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_dependencies",
            new=AsyncMock(return_value=_dependencies(results_total=4)),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.update_subject",
            new=AsyncMock(return_value=subject),
        ),
    ):
        result = await SubjectService.archive_subject(db, admin, subject.id)

    assert result.archived_at is not None
    assert result.archived_by_admin_id == admin.id
    assert result.is_active is False


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
        result = await SubjectService.restore_subject(db, _actor(tenant_id), subject.id)

    assert result.is_active is False
    assert result.archived_at is None
    assert result.archived_by_admin_id is None


@pytest.mark.asyncio
async def test_restore_rejects_non_archived_subject() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)

    with patch(
        "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
        new=AsyncMock(return_value=subject),
    ):
        with pytest.raises(ConflictException, match="Only archived subjects"):
            await SubjectService.restore_subject(AsyncMock(), _actor(tenant_id), subject.id)


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
            await SubjectService.activate_subject(AsyncMock(), _actor(tenant_id), subject.id)


@pytest.mark.asyncio
async def test_unused_subject_can_be_hard_deleted_even_while_active() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=True)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.count_dependencies",
            new=AsyncMock(return_value=_dependencies()),
        ),
        patch(
            "app.modules.subjects.service.SubjectRepository.delete_subject",
            new=AsyncMock(),
        ) as delete_subject,
    ):
        response = await SubjectService.hard_delete_subject(db, _actor(tenant_id), subject.id)

    assert response.id == subject.id
    delete_subject.assert_awaited_once_with(db=db, subject=subject)


@pytest.mark.asyncio
async def test_historical_usage_permanently_blocks_hard_delete() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
    counts = _dependencies(report_card_lines_total=1)

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
        with pytest.raises(ConflictException, match="permanently deleted") as exc_info:
            await SubjectService.hard_delete_subject(AsyncMock(), _actor(tenant_id), subject.id)

    assert exc_info.value.payload == {"dependency_counts": counts}


@pytest.mark.asyncio
async def test_teacher_cannot_fetch_inactive_subject() -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)

    with patch(
        "app.modules.subjects.service.SubjectRepository.get_subject_by_id",
        new=AsyncMock(return_value=subject),
    ):
        with pytest.raises(NotFoundException):
            await SubjectService.get_subject(AsyncMock(), _teacher(tenant_id), subject.id)


@pytest.mark.asyncio
async def test_teacher_listing_is_forced_to_active_repository_path() -> None:
    tenant_id = uuid.uuid4()
    teacher = _teacher(tenant_id)
    db = AsyncMock()

    with patch(
        "app.modules.subjects.service.SubjectRepository.list_subjects_for_teacher",
        new=AsyncMock(return_value=([], 0)),
    ) as list_subjects:
        await SubjectService.list_subjects(
            db,
            teacher,
            is_active=False,
            include_archived=True,
            lifecycle_status="inactive",
        )

    list_subjects.assert_awaited_once_with(
        db=db,
        tenant_id=tenant_id,
        teacher_id=teacher.id,
        skip=0,
        limit=100,
        search=None,
    )


@pytest.mark.asyncio
async def test_repository_dependency_snapshot_is_single_query_shape() -> None:
    tenant_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    result = MagicMock()
    result.one.return_value = SimpleNamespace(
        curriculum_subjects_total=2,
        curriculum_subjects_live=1,
        teacher_links_total=3,
        teacher_links_live=0,
        teacher_assignments_total=4,
        teacher_assignments_live=1,
        results_total=5,
        results_live=0,
        report_card_lines_total=6,
        report_card_lines_live=0,
    )
    db = AsyncMock()
    db.execute.return_value = result

    counts = await SubjectRepository.count_dependencies(db, tenant_id, subject_id)

    assert counts == {
        "curriculum_subjects_total": 2,
        "curriculum_subjects_live": 1,
        "teacher_links_total": 3,
        "teacher_links_live": 0,
        "teacher_assignments_total": 4,
        "teacher_assignments_live": 1,
        "results_total": 5,
        "results_live": 0,
        "report_card_lines_total": 6,
        "report_card_lines_live": 0,
    }
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_subject_mutations_use_academic_write_guard(_allow_academic_writes) -> None:
    tenant_id = uuid.uuid4()
    subject = _subject(tenant_id, active=False)
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
        await SubjectService.activate_subject(db, _actor(tenant_id), subject.id)

    _allow_academic_writes.assert_awaited_once_with(db, tenant_id=tenant_id)
