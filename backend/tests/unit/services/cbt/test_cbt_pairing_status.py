from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundException
from app.modules.cbt.pairing.service import CBTPairingStatusService


@pytest.mark.asyncio
async def test_status_lookup_is_tenant_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.modules.cbt.pairing.service.hash_pairing_code",
        lambda value: "digest",
    )
    monkeypatch.setattr(
        "app.modules.cbt.pairing.service.CBTPairingCodeRepository.get_by_hash",
        AsyncMock(return_value=SimpleNamespace(tenant_id=uuid4())),
    )

    with pytest.raises(NotFoundException):
        await CBTPairingStatusService.get_status(
            object(),  # type: ignore[arg-type]
            admin=SimpleNamespace(tenant_id=uuid4()),
            pairing_code="ABCD-EFGH",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"used_at": datetime.now(timezone.utc), "used_by_server_id": uuid4()}, "paired"),
        ({"invalidated_at": datetime.now(timezone.utc)}, "invalidated"),
        ({"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}, "expired"),
        ({}, "pending"),
    ],
)
async def test_status_lookup_reports_current_state(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict,
    expected: str,
) -> None:
    tenant_id = uuid4()
    values = {
        "tenant_id": tenant_id,
        "used_at": None,
        "used_by_server_id": None,
        "invalidated_at": None,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    values.update(overrides)

    monkeypatch.setattr(
        "app.modules.cbt.pairing.service.hash_pairing_code",
        lambda value: "digest",
    )
    monkeypatch.setattr(
        "app.modules.cbt.pairing.service.CBTPairingCodeRepository.get_by_hash",
        AsyncMock(return_value=SimpleNamespace(**values)),
    )

    result = await CBTPairingStatusService.get_status(
        object(),  # type: ignore[arg-type]
        admin=SimpleNamespace(tenant_id=tenant_id),
        pairing_code="ABCD-EFGH",
    )

    assert result.status == expected
