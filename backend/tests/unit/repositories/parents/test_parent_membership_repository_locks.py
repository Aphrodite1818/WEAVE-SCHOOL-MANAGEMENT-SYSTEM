from __future__ import annotations

import uuid

import pytest
from sqlalchemy.dialects import postgresql

import app.models  # noqa: F401
from app.modules.parents.repository import ParentMembershipRepository


class _EmptyResult:
    def scalar_one_or_none(self) -> None:
        return None


class _CapturingSession:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _EmptyResult()


@pytest.mark.asyncio
async def test_account_tenant_lock_targets_parent_memberships_only() -> None:

    db = _CapturingSession()

    await ParentMembershipRepository.get_by_account_and_tenant(
        db,  # type: ignore[arg-type]
        uuid.uuid4(),
        uuid.uuid4(),
        lock=True,
    )

    sql = str(db.statement.compile(dialect=postgresql.dialect()))

    assert "LEFT OUTER JOIN public.parent_accounts" in sql
    assert "FOR UPDATE OF parent_memberships" in sql
