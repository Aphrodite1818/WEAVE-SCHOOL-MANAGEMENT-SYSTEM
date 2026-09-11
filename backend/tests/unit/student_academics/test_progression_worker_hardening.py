from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.classes.models import AcademicCategory
from app.modules.classes.repository import AcademicLevelRepository
from app.modules.student_academics.lifecycle_repository import StudentProgressionRepository
from app.modules.student_academics.models import (
    AcademicSessionStatus,
    StudentProgressionItemStatus,
)
from app.modules.student_academics.progression_service import AcademicProgressionService
from app.modules.students.repository import StudentEnrollmentRepository
from app.tenant_management.models import InstitutionType
from app.tenant_management.repository import TenantRepository


@pytest.mark.asyncio
async def test_resolve_next_level_uses_preloaded_progression_catalog(monkeypatch) -> None:
    tenant_id = uuid4()
    current = SimpleNamespace(
        id=uuid4(),
        name="JSS One",
        category=AcademicCategory.JUNIOR_SECONDARY,
        position=1,
    )
    target = SimpleNamespace(
        id=uuid4(),
        name="JSS Two",
        category=AcademicCategory.JUNIOR_SECONDARY,
        position=2,
    )
    tenant = SimpleNamespace(institution_type=InstitutionType.SECONDARY_SCHOOL)

    get_tenant = AsyncMock(side_effect=AssertionError("tenant must be preloaded"))
    list_levels = AsyncMock(side_effect=AssertionError("levels must be preloaded"))
    monkeypatch.setattr(TenantRepository, "get_by_id", get_tenant)
    monkeypatch.setattr(AcademicLevelRepository, "list_for_tenant", list_levels)

    resolved = await AcademicProgressionService.resolve_next_level(
        AsyncMock(),
        tenant_id=tenant_id,
        current_level=current,
        tenant=tenant,
        levels=[current, target],
    )

    assert resolved is target
    get_tenant.assert_not_awaited()
    list_levels.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_next_enrollment_reuses_future_target_session_enrollment(monkeypatch) -> None:
    tenant_id = uuid4()
    student_id = uuid4()
    target_level_id = uuid4()
    existing_enrollment_id = uuid4()
    future_start = date.today() + timedelta(days=30)
    student = SimpleNamespace(id=student_id)
    item = SimpleNamespace(
        to_enrollment_id=None,
        to_level_id=None,
        to_class_id=None,
        status=StudentProgressionItemStatus.BLOCKED,
        processed_at=None,
    )
    target_level = SimpleNamespace(id=target_level_id, name="JSS Two")
    next_session = SimpleNamespace(
        id=uuid4(),
        status=AcademicSessionStatus.DRAFT,
        start_date=future_start,
    )
    existing_target = SimpleNamespace(
        id=existing_enrollment_id,
        student_id=student_id,
        academic_session_id=next_session.id,
        academic_level_id=target_level_id,
        class_id=None,
        started_on=future_start,
        ended_on=None,
    )

    add_enrollment = AsyncMock(side_effect=AssertionError("must not duplicate enrollment"))
    save_item = AsyncMock(side_effect=lambda _db, value: value)
    monkeypatch.setattr(StudentEnrollmentRepository, "add", add_enrollment)
    monkeypatch.setattr(StudentProgressionRepository, "save_item", save_item)

    result = await AcademicProgressionService._create_next_enrollment(
        SimpleNamespace(),
        tenant_id=tenant_id,
        student=student,
        item=item,
        target_level=target_level,
        next_session=next_session,
        created_by_admin_id=uuid4(),
        existing_target=existing_target,
        target_lookup_complete=True,
    )

    assert result is item
    assert item.to_enrollment_id == existing_enrollment_id
    assert item.to_level_id == target_level_id
    assert item.status == StudentProgressionItemStatus.COMPLETED
    add_enrollment.assert_not_awaited()
    save_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_next_enrollment_does_not_reuse_ended_target_segment(monkeypatch) -> None:
    tenant_id = uuid4()
    student_id = uuid4()
    target_level_id = uuid4()
    created_enrollment_id = uuid4()
    future_start = date.today() + timedelta(days=30)
    student = SimpleNamespace(id=student_id)
    item = SimpleNamespace(
        to_enrollment_id=None,
        to_level_id=None,
        to_class_id=None,
        status=StudentProgressionItemStatus.BLOCKED,
        processed_at=None,
    )
    target_level = SimpleNamespace(id=target_level_id, name="JSS Two")
    next_session = SimpleNamespace(
        id=uuid4(),
        status=AcademicSessionStatus.DRAFT,
        start_date=future_start,
    )
    stale_target = SimpleNamespace(
        id=uuid4(),
        student_id=student_id,
        academic_session_id=next_session.id,
        academic_level_id=target_level_id,
        class_id=None,
        started_on=future_start - timedelta(days=10),
        ended_on=future_start - timedelta(days=1),
    )

    add_enrollment = AsyncMock(return_value=SimpleNamespace(id=created_enrollment_id))
    save_item = AsyncMock(side_effect=lambda _db, value: value)
    monkeypatch.setattr(StudentEnrollmentRepository, "add", add_enrollment)
    monkeypatch.setattr(StudentProgressionRepository, "save_item", save_item)

    result = await AcademicProgressionService._create_next_enrollment(
        SimpleNamespace(),
        tenant_id=tenant_id,
        student=student,
        item=item,
        target_level=target_level,
        next_session=next_session,
        created_by_admin_id=uuid4(),
        existing_target=stale_target,
        target_lookup_complete=True,
    )

    assert result is item
    assert item.to_enrollment_id == created_enrollment_id
    assert item.to_level_id == target_level_id
    assert item.status == StudentProgressionItemStatus.COMPLETED
    add_enrollment.assert_awaited_once()
    created = add_enrollment.await_args.args[1]
    assert created.academic_session_id == next_session.id
    assert created.started_on == future_start
    save_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_next_enrollment_rejects_conflicting_target_session_enrollment(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    student = SimpleNamespace(id=uuid4())
    item = SimpleNamespace()
    target_level = SimpleNamespace(id=uuid4(), name="JSS Two")
    next_session = SimpleNamespace(
        id=uuid4(),
        status=AcademicSessionStatus.DRAFT,
        start_date=date.today() + timedelta(days=30),
    )
    existing_target = SimpleNamespace(
        id=uuid4(),
        academic_session_id=next_session.id,
        academic_level_id=uuid4(),
        class_id=None,
        started_on=next_session.start_date,
        ended_on=None,
    )
    add_enrollment = AsyncMock()
    monkeypatch.setattr(StudentEnrollmentRepository, "add", add_enrollment)

    with pytest.raises(ConflictException, match="different enrollment"):
        await AcademicProgressionService._create_next_enrollment(
            SimpleNamespace(),
            tenant_id=tenant_id,
            student=student,
            item=item,
            target_level=target_level,
            next_session=next_session,
            created_by_admin_id=uuid4(),
            existing_target=existing_target,
            target_lookup_complete=True,
        )

    add_enrollment.assert_not_awaited()
