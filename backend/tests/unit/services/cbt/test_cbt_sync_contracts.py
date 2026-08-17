from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.cbt.sync.enums import CBTSyncEntityType, CBTSyncOperation
from app.modules.cbt.sync.repository import CBTSyncRepository
from app.modules.cbt.sync.schemas import CBTSyncMutation
from app.modules.cbt.sync.service import CBTSyncService


def change(cursor: int):
    return SimpleNamespace(
        id=uuid4(),
        cursor=cursor,
        entity_type=CBTSyncEntityType.ACADEMIC_LEVEL,
        entity_id=uuid4(),
        operation=CBTSyncOperation.UPDATED,
        schema_version=2,
        payload={"id": str(uuid4()), "name": f"Level {cursor}"},
        created_at=datetime(2026, 8, 17, 12, cursor, tzinfo=timezone.utc),
    )


def test_mutation_uses_v2_and_requires_full_payload_for_upsert() -> None:
    mutation = CBTSyncMutation(
        entity_type=CBTSyncEntityType.SUBJECT,
        entity_id=uuid4(),
        operation=CBTSyncOperation.UPDATED,
        payload={"name": "Mathematics"},
    )
    assert mutation.schema_version == 2

    with pytest.raises(ValidationError, match="require a payload"):
        CBTSyncMutation(
            entity_type=CBTSyncEntityType.SUBJECT,
            entity_id=uuid4(),
            operation=CBTSyncOperation.UPDATED,
        )


def test_delete_is_a_null_tombstone() -> None:
    mutation = CBTSyncMutation(
        entity_type=CBTSyncEntityType.CLASS,
        entity_id=uuid4(),
        operation=CBTSyncOperation.DELETED,
    )
    assert mutation.payload is None

    with pytest.raises(ValidationError, match="null tombstone"):
        CBTSyncMutation(
            entity_type=CBTSyncEntityType.CLASS,
            entity_id=uuid4(),
            operation=CBTSyncOperation.DELETED,
            payload={"stale": True},
        )


def test_serialize_change_uses_created_at_as_occurred_at() -> None:
    row = change(1)
    response = CBTSyncService.serialize_change(row)
    assert response.event_id == row.id
    assert response.cursor == 1
    assert response.occurred_at == row.created_at
    assert response.schema_version == 2


@pytest.mark.asyncio
async def test_delta_recovery_is_ordered_paginated_and_tenant_scoped(monkeypatch) -> None:
    tenant_id = uuid4()
    rows = [change(11), change(12), change(13)]
    get_changes = AsyncMock(return_value=rows)
    monkeypatch.setattr(CBTSyncRepository, "get_changes_after", get_changes)

    response = await CBTSyncService.get_changes_after(
        AsyncMock(),
        tenant_id=tenant_id,
        after_cursor=10,
        limit=2,
    )

    assert response.from_cursor == 10
    assert response.next_cursor == 12
    assert response.has_more is True
    assert [item.cursor for item in response.changes] == [11, 12]
    get_changes.assert_awaited_once()
    assert get_changes.await_args.kwargs == {
        "tenant_id": tenant_id,
        "after_cursor": 10,
        "limit": 2,
    }


@pytest.mark.asyncio
async def test_empty_delta_preserves_last_applied_cursor(monkeypatch) -> None:
    monkeypatch.setattr(
        CBTSyncRepository,
        "get_changes_after",
        AsyncMock(return_value=[]),
    )

    response = await CBTSyncService.get_changes_after(
        AsyncMock(),
        tenant_id=uuid4(),
        after_cursor=44,
        limit=100,
    )

    assert response.next_cursor == 44
    assert response.has_more is False
    assert response.changes == []
