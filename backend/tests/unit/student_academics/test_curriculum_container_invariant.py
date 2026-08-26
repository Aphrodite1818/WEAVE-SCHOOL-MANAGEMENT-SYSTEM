from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.cbt.sync.projectors.curriculum import project_curriculum
from app.modules.classes.models import AcademicCategory, AcademicLevel, AcademicLevelStatus
from app.modules.classes.service import AcademicLevelService
from app.modules.student_academics.curriculum_models import Curriculum
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def _admin(tenant_id: uuid.UUID) -> TenantAdmin:
    return TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.test",
        password_hash="hashed",
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )


def _level(tenant_id: uuid.UUID, status: AcademicLevelStatus) -> AcademicLevel:
    now = datetime.now(timezone.utc)
    return AcademicLevel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="JSS1",
        normalized_name="jss1",
        category=AcademicCategory.JUNIOR_SECONDARY,
        position=1,
        status=status,
        created_at=now,
        updated_at=now,
    )


def _curriculum(tenant_id: uuid.UUID, level_id: uuid.UUID) -> Curriculum:
    now = datetime.now(timezone.utc)
    return Curriculum(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        academic_level_id=level_id,
        created_at=now,
        updated_at=now,
    )


def _db_with_scalar(value):
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    db.execute.return_value = result
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def test_curriculum_parent_fk_restricts_academic_level_deletion() -> None:
    fk = next(iter(Curriculum.__table__.columns.academic_level_id.foreign_keys))
    assert fk.ondelete == "RESTRICT"


@pytest.mark.asyncio
async def test_first_level_activation_creates_exactly_one_curriculum_in_same_transaction() -> None:
    tenant_id = uuid.uuid4()
    level = _level(tenant_id, AcademicLevelStatus.DRAFT)
    db = _db_with_scalar(None)

    with (
        patch(
            "app.modules.classes.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelService._validate_publication_contract",
            new=AsyncMock(),
        ),
    ):
        response = await AcademicLevelService.activate(
            db=db,
            actor=_admin(tenant_id),
            academic_level_id=level.id,
        )

    curriculum_adds = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], Curriculum)
    ]
    assert response.status == AcademicLevelStatus.ACTIVE
    assert len(curriculum_adds) == 1
    assert curriculum_adds[0].tenant_id == tenant_id
    assert curriculum_adds[0].academic_level_id == level.id
    assert db.flush.await_count == 2
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_level_reactivation_reuses_existing_curriculum() -> None:
    tenant_id = uuid.uuid4()
    level = _level(tenant_id, AcademicLevelStatus.INACTIVE)
    existing = _curriculum(tenant_id, level.id)
    db = _db_with_scalar(existing)

    with (
        patch(
            "app.modules.classes.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelService._validate_publication_contract",
            new=AsyncMock(),
        ) as publication_contract,
    ):
        response = await AcademicLevelService.activate(
            db=db,
            actor=_admin(tenant_id),
            academic_level_id=level.id,
        )

    assert response.status == AcademicLevelStatus.ACTIVE
    assert not any(
        isinstance(call.args[0], Curriculum) for call in db.add.call_args_list
    )
    publication_contract.assert_not_awaited()
    assert db.flush.await_count == 1


@pytest.mark.asyncio
async def test_get_curriculum_is_read_only() -> None:
    tenant_id = uuid.uuid4()
    level = _level(tenant_id, AcademicLevelStatus.ACTIVE)
    curriculum = _curriculum(tenant_id, level.id)
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()

    curriculum_result = MagicMock()
    curriculum_result.scalar_one_or_none.return_value = curriculum
    subjects_result = MagicMock()
    subjects_result.all.return_value = []
    db.execute.side_effect = [curriculum_result, subjects_result]

    with patch(
        "app.modules.student_academics.curriculum_v2_service.AcademicLevelRepository.get_by_id",
        new=AsyncMock(side_effect=[level, level]),
    ):
        response = await AcademicCurriculumService.get_curriculum(
            db=db,
            tenant_id=tenant_id,
            level_id=level.id,
        )

    assert response.id == curriculum.id
    assert response.academic_level_id == level.id
    assert response.level_name == level.name
    db.add.assert_not_called()
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_curriculum_never_lazy_creates_missing_container() -> None:
    tenant_id = uuid.uuid4()
    level = _level(tenant_id, AcademicLevelStatus.ACTIVE)
    db = _db_with_scalar(None)

    with patch(
        "app.modules.student_academics.curriculum_v2_service.AcademicLevelRepository.get_by_id",
        new=AsyncMock(return_value=level),
    ):
        with pytest.raises(NotFoundException, match="Curriculum not found"):
            await AcademicCurriculumService.get_curriculum(
                db=db,
                tenant_id=tenant_id,
                level_id=level.id,
            )

    db.add.assert_not_called()
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_inactive_level_cannot_receive_new_curriculum_subjects() -> None:
    tenant_id = uuid.uuid4()
    level = _level(tenant_id, AcademicLevelStatus.INACTIVE)
    db = MagicMock()
    db.execute = AsyncMock()

    with patch(
        "app.modules.student_academics.curriculum_v2_service.AcademicLevelRepository.get_by_id",
        new=AsyncMock(return_value=level),
    ):
        with pytest.raises(ConflictException, match="must be active"):
            await AcademicCurriculumService._curriculum(
                db=db,
                tenant_id=tenant_id,
                level_id=level.id,
                require_active_level=True,
            )

    db.execute.assert_not_awaited()


def test_cbt_curriculum_visibility_inherits_inactive_level() -> None:
    tenant_id = uuid.uuid4()
    level = _level(tenant_id, AcademicLevelStatus.INACTIVE)
    curriculum = _curriculum(tenant_id, level.id)
    result = MagicMock()
    result.first.return_value = (curriculum, level)
    session = MagicMock()
    session.execute.return_value = result

    assert project_curriculum(session, tenant_id, curriculum.id) is None
