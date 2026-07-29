from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.announcements.service import AnnouncementService
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
