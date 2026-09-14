from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.classes.repository import ClassRoomRepository


@pytest.mark.asyncio
async def test_get_by_id_lock_targets_only_classroom_table() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    await ClassRoomRepository.get_by_id(
        db,
        tenant_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        lock=True,
    )

    query = db.execute.await_args.args[0]
    sql = str(query.compile(dialect=postgresql.dialect()))

    # ClassRoom relationships are joined for the response, but PostgreSQL must
    # lock only the concrete class row. A blanket FOR UPDATE on these outer
    # joins raises FeatureNotSupportedError.
    assert "LEFT OUTER JOIN" in sql
    assert "FOR UPDATE OF classes" in sql
