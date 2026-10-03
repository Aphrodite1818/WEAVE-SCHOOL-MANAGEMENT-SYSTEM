from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import UnauthorizedException
from app.modules.cbt.auth.schemas import AuthenticatedCBTActor, AuthenticatedCBTServer
from app.modules.cbt.dependencies import get_current_cbt_actor
from app.modules.cbt.enums import CBTServerStatus


def _server() -> AuthenticatedCBTServer:
    return AuthenticatedCBTServer(
        server_id=uuid4(),
        credential_id=uuid4(),
        tenant_id=uuid4(),
        server_name="School CBT",
        status=CBTServerStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_actor_dependency_requires_actor_authorization_header() -> None:
    with pytest.raises(UnauthorizedException):
        await get_current_cbt_actor(
            db=AsyncMock(),
            current_server=_server(),
            actor_authorization=None,
        )


@pytest.mark.asyncio
async def test_actor_dependency_delegates_to_cbt_auth_service(monkeypatch) -> None:
    server = _server()
    expected = AuthenticatedCBTActor(
        authorization_id=uuid4(),
        tenant_id=server.tenant_id,
        actor_id=uuid4(),
        membership_id=uuid4(),
        role="teacher",
    )
    authenticate = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "app.modules.cbt.dependencies.CBTActorAuthorizationService.authenticate_actor",
        authenticate,
    )
    db = AsyncMock()

    result = await get_current_cbt_actor(
        db=db,
        current_server=server,
        actor_authorization="wcbt_acc_example",
    )

    assert result == expected
    authenticate.assert_awaited_once_with(
        db,
        current_server=server,
        access_token="wcbt_acc_example",
    )
