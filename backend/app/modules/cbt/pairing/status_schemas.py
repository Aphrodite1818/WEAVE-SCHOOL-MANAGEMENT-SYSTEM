"""Schemas for tenant-admin pairing status checks."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PairingStatusRequest(BaseModel):
    """Identify the exact pairing challenge being monitored by the admin UI."""

    model_config = ConfigDict(str_strip_whitespace=True)

    pairing_code: str = Field(..., min_length=8, max_length=20)


class PairingStatusResponse(BaseModel):
    """Current lifecycle state of one tenant-owned pairing challenge."""

    status: Literal["pending", "paired", "expired", "invalidated"]
    expires_at: datetime
    server_id: UUID | None = None
