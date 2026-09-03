from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.modules.cbt.sync.enums import CBTSyncEntityType, CBTSyncOperation

SYNC_SCHEMA_VERSION = 5


class CBTSyncMutation(BaseModel):
    """Internal representation of one CBT-visible business mutation."""

    entity_type: CBTSyncEntityType
    entity_id: uuid.UUID
    operation: CBTSyncOperation
    schema_version: int = Field(default=SYNC_SCHEMA_VERSION, ge=1)
    payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "CBTSyncMutation":
        if (
            self.operation in {CBTSyncOperation.CREATED, CBTSyncOperation.UPDATED}
            and self.payload is None
        ):
            raise ValueError("Created and updated CBT sync mutations require a payload.")
        if self.operation == CBTSyncOperation.DELETED and self.payload is not None:
            raise ValueError("Deleted CBT sync mutations must use a null tombstone payload.")
        return self


class CBTSyncChangeResponse(BaseModel):
    """One durable synchronization change returned through cursor recovery."""

    event_id: uuid.UUID
    cursor: int
    entity_type: CBTSyncEntityType
    entity_id: uuid.UUID
    operation: CBTSyncOperation
    schema_version: int
    payload: dict[str, Any] | None
    occurred_at: datetime


class CBTSyncDeltaResponse(BaseModel):
    """Ordered batch of synchronization changes returned during recovery."""

    from_cursor: int
    next_cursor: int
    has_more: bool
    changes: list[CBTSyncChangeResponse]


class CBTSyncNotification(BaseModel):
    """Tiny PostgreSQL/WebSocket high-water notification."""

    tenant_id: uuid.UUID
    cursor: int = Field(ge=1)
