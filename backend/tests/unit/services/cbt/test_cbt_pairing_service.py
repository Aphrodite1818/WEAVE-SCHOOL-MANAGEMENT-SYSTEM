from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException, ConflictException
from app.modules.cbt.pairing.schemas import CBT_SERVER_REVOKE_CONFIRMATION_LITERAL
from app.modules.cbt.pairing.service import CBTPairingService


@pytest.mark.asyncio
async def test_ensure_server_name_available_raises_conflict_for_normalized_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_server = SimpleNamespace(id=uuid4())

    monkeypatch.setattr(
        "app.modules.cbt.pairing.service.CBTServerRepository.get_by_tenant_and_normalized_name",
        AsyncMock(return_value=existing_server),
    )

    with pytest.raises(
        ConflictException,
        match="already exists for this tenant",
    ):
        await CBTPairingService._ensure_server_name_available(
            object(),  # type: ignore[arg-type]
            tenant_id=uuid4(),
            normalized_name="ICT CBT Lab",
        )


def test_validate_revocation_request_requires_reason_and_literal() -> None:
    with pytest.raises(BadRequestException, match="reason is required"):
        CBTPairingService._validate_revocation_request(
            reason="   ",
            confirmation_literal=CBT_SERVER_REVOKE_CONFIRMATION_LITERAL,
        )

    with pytest.raises(BadRequestException, match="Type REVOKE SERVER"):
        CBTPairingService._validate_revocation_request(
            reason="Decommissioned lab machine",
            confirmation_literal="REVOKE",
        )


def test_validate_revocation_request_returns_normalized_reason() -> None:
    assert CBTPairingService._validate_revocation_request(
        reason="  Decommissioned lab machine  ",
        confirmation_literal=CBT_SERVER_REVOKE_CONFIRMATION_LITERAL,
    ) == "Decommissioned lab machine"


@pytest.mark.asyncio
async def test_revoke_server_rejects_invalid_literal_before_loading_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_server = AsyncMock()
    monkeypatch.setattr(
        CBTPairingService,
        "_get_server_for_admin",
        get_server,
    )

    with pytest.raises(BadRequestException, match="Type REVOKE SERVER"):
        await CBTPairingService.revoke_server(
            object(),  # type: ignore[arg-type]
            admin=SimpleNamespace(),
            server_id=uuid4(),
            reason="Decommissioned lab machine",
            confirmation_literal="REVOKE",
        )

    get_server.assert_not_awaited()
