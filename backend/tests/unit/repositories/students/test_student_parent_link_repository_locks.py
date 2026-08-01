from __future__ import annotations

import uuid

import pytest
from sqlalchemy.dialects import postgresql

import app.models  # noqa: F401
from app.modules.students.models import StudentParentLinkStatus
from app.modules.students.repository import StudentParentLinkRepository


class _ScalarResult:
    def unique(self) -> "_ScalarResult":
        return self

    def all(self) -> list[object]:
        return []


class _Result:
    def scalars(self) -> _ScalarResult:
        return _ScalarResult()


class _CapturingSession:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _Result()


@pytest.mark.asyncio
async def test_list_for_student_lock_targets_student_parent_links_only() -> None:
    
    db = _CapturingSession()

    await StudentParentLinkRepository.list_for_student(
        db,  # type: ignore[arg-type]
        uuid.uuid4(),
        uuid.uuid4(),
        statuses=[StudentParentLinkStatus.ACTIVE],
        lock=True,
    )

    sql = str(db.statement.compile(dialect=postgresql.dialect()))

    assert "LEFT OUTER JOIN public.parent_memberships" in sql
    assert "LEFT OUTER JOIN public.parent_accounts" in sql
    assert "FOR UPDATE OF student_parent_links" in sql


@pytest.mark.asyncio
async def test_list_for_membership_lock_targets_student_parent_links_only() -> None:
    
    db = _CapturingSession()

    await StudentParentLinkRepository.list_for_membership(
        db,  # type: ignore[arg-type]
        uuid.uuid4(),
        uuid.uuid4(),
        statuses=[StudentParentLinkStatus.ACTIVE],
        lock=True,
    )

    sql = str(db.statement.compile(dialect=postgresql.dialect()))

    assert "LEFT OUTER JOIN public.students" in sql
    assert "FOR UPDATE OF student_parent_links" in sql
