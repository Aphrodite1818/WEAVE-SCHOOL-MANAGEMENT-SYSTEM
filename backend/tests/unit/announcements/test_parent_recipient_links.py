from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException
from app.modules.announcements.models import AnnouncementReadStatus
from app.modules.announcements.repository import AnnouncementReadRepository
from app.modules.announcements.service import AnnouncementService
from app.modules.students.models import Student
from app.modules.students.models import StudentParentLinkStatus


class _ScalarResult:
    def scalars(self):
        return self

    def all(self):
        return []


class _Db:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _ScalarResult()


@pytest.mark.asyncio
async def test_parent_student_ids_filters_to_accessible_link_statuses() -> None:
    db = _Db()
    parent = SimpleNamespace(tenant_id=uuid4(), id=uuid4())

    await AnnouncementService._parent_student_ids(db, parent)

    sql = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert StudentParentLinkStatus.ACTIVE.value in sql
    assert StudentParentLinkStatus.READ_ONLY.value in sql
    assert StudentParentLinkStatus.ALUMNI_READ_ONLY.value in sql
    assert StudentParentLinkStatus.ENDED.value not in sql


@pytest.mark.asyncio
async def test_feed_excludes_announcements_published_before_actor_was_created() -> None:
    actor_created_at = datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc)
    student = Student(
        id=uuid4(),
        tenant_id=uuid4(),
        class_id=uuid4(),
        admission_number="STU-001",
        created_at=actor_created_at,
    )

    base, _, _ = await AnnouncementService._feed_base_query(_Db(), student)

    sql = str(base.compile(compile_kwargs={"literal_binds": True}))
    assert "coalesce(" in sql
    assert "announcements.publish_at" in sql
    assert "announcements.created_at" in sql
    assert "2026-07-29" in sql


@pytest.mark.asyncio
async def test_mark_read_checks_exact_feed_visibility_instead_of_first_page(monkeypatch) -> None:
    tenant_id = uuid4()
    announcement_id = uuid4()
    actor = Student(
        id=uuid4(),
        tenant_id=tenant_id,
        class_id=uuid4(),
        admission_number="STU-002",
        created_at=datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc),
    )

    async def fail_if_feed_is_used(*args, **kwargs):
        raise AssertionError("mark_read should not validate visibility from a limited feed page")

    async def visible_announcement(*args, **kwargs):
        return SimpleNamespace(id=announcement_id)

    async def upsert_read_state(*args, **kwargs):
        return SimpleNamespace(
            tenant_id=tenant_id,
            announcement_id=announcement_id,
            actor_type=kwargs["actor_type"],
            actor_id=actor.id,
            status=kwargs["status"],
        )

    async def noop(*args, **kwargs):
        return None

    class _CommitDb:
        async def commit(self):
            return None

    monkeypatch.setattr(AnnouncementService, "feed", staticmethod(fail_if_feed_is_used))
    monkeypatch.setattr(AnnouncementService, "_visible_feed_announcement", staticmethod(visible_announcement))
    monkeypatch.setattr(AnnouncementReadRepository, "upsert_read_state", staticmethod(upsert_read_state))
    monkeypatch.setattr(AnnouncementService, "_invalidate_after_read", staticmethod(noop))
    monkeypatch.setattr("app.modules.announcements.service.flush_cache_invalidation_events", noop)

    read = await AnnouncementService.mark_read(
        _CommitDb(),
        actor=actor,
        announcement_id=announcement_id,
        status=AnnouncementReadStatus.READ,
    )

    assert read.announcement_id == announcement_id
    assert read.status == AnnouncementReadStatus.READ


@pytest.mark.asyncio
async def test_feed_excludes_deleted_read_states() -> None:
    student = Student(
        id=uuid4(),
        tenant_id=uuid4(),
        class_id=uuid4(),
        admission_number="STU-003",
        created_at=datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc),
    )

    base, _, _ = await AnnouncementService._feed_base_query(_Db(), student)

    sql = str(base.compile(compile_kwargs={"literal_binds": True}))
    assert "announcement_reads.status = 'DELETED'" in sql


@pytest.mark.asyncio
async def test_delete_notification_requires_existing_read_state(monkeypatch) -> None:
    actor = Student(
        id=uuid4(),
        tenant_id=uuid4(),
        class_id=uuid4(),
        admission_number="STU-004",
        created_at=datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc),
    )

    async def visible_announcement(*args, **kwargs):
        return SimpleNamespace(id=kwargs["announcement_id"])

    async def no_read_state(*args, **kwargs):
        return None

    monkeypatch.setattr(AnnouncementService, "_visible_feed_announcement", staticmethod(visible_announcement))
    monkeypatch.setattr(AnnouncementReadRepository, "get_read_state", staticmethod(no_read_state))

    with pytest.raises(BadRequestException) as exc_info:
        await AnnouncementService.delete_read_notification(
            SimpleNamespace(),
            actor=actor,
            announcement_id=uuid4(),
        )

    assert "Only read notifications can be deleted" in str(exc_info.value)
