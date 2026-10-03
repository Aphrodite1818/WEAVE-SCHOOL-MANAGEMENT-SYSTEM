from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.modules.cbt.auth.refresh_recovery import (
    CBTActorRefreshRecoveryService,
    CBTRefreshRecoveryUnavailable,
)
from app.modules.cbt.auth.schemas import CBTActorTokenPair
from app.modules.cbt.auth.security import hash_actor_token


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def set(self, key: str, value: str, *, ex: int) -> None:
        self.values[key] = value
        self.ttls[key] = ex

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def unlink(self, key: str) -> int:
        existed = key in self.values
        self.values.pop(key, None)
        self.ttls.pop(key, None)
        return int(existed)


def _pair() -> CBTActorTokenPair:
    now = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    return CBTActorTokenPair(
        access_token="wcbt_acc_super-secret-access",
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token="wcbt_ref_super-secret-refresh",
        refresh_token_expires_at=now + timedelta(hours=8),
    )


@pytest.mark.asyncio
async def test_recovery_receipt_encrypts_tokens_and_recovers_exact_pair(monkeypatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(
        "app.modules.cbt.auth.refresh_recovery.get_runtime_redis",
        lambda: redis,
    )
    server_id = uuid4()
    authorization_id = uuid4()
    operation_id = uuid4()
    old_refresh_hash = hash_actor_token("wcbt_ref_old")
    token_pair = _pair()

    await CBTActorRefreshRecoveryService.store(
        server_id=server_id,
        authorization_id=authorization_id,
        refresh_token_hash=old_refresh_hash,
        idempotency_key=operation_id,
        token_pair=token_pair,
        ttl_seconds=7200,
    )

    assert len(redis.values) == 1
    raw_receipt = next(iter(redis.values.values()))
    receipt = json.loads(raw_receipt)
    assert token_pair.access_token not in raw_receipt
    assert token_pair.refresh_token not in raw_receipt
    assert receipt["version"] == 1
    assert receipt["operation_id"] == str(operation_id)
    assert redis.ttls[next(iter(redis.values))] == 7200

    recovered = await CBTActorRefreshRecoveryService.recover(
        server_id=server_id,
        authorization_id=authorization_id,
        refresh_token_hash=old_refresh_hash,
        idempotency_key=operation_id,
    )

    assert recovered == token_pair


@pytest.mark.asyncio
async def test_recovery_rejects_different_operation_or_server(monkeypatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(
        "app.modules.cbt.auth.refresh_recovery.get_runtime_redis",
        lambda: redis,
    )
    server_id = uuid4()
    authorization_id = uuid4()
    operation_id = uuid4()
    old_refresh_hash = hash_actor_token("wcbt_ref_old")

    await CBTActorRefreshRecoveryService.store(
        server_id=server_id,
        authorization_id=authorization_id,
        refresh_token_hash=old_refresh_hash,
        idempotency_key=operation_id,
        token_pair=_pair(),
        ttl_seconds=7200,
    )

    wrong_operation = await CBTActorRefreshRecoveryService.recover(
        server_id=server_id,
        authorization_id=authorization_id,
        refresh_token_hash=old_refresh_hash,
        idempotency_key=uuid4(),
    )
    wrong_server = await CBTActorRefreshRecoveryService.recover(
        server_id=uuid4(),
        authorization_id=authorization_id,
        refresh_token_hash=old_refresh_hash,
        idempotency_key=operation_id,
    )

    assert wrong_operation is None
    assert wrong_server is None


@pytest.mark.asyncio
async def test_corrupted_matching_receipt_fails_closed_without_exposing_tokens(monkeypatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(
        "app.modules.cbt.auth.refresh_recovery.get_runtime_redis",
        lambda: redis,
    )
    server_id = uuid4()
    authorization_id = uuid4()
    operation_id = uuid4()
    old_refresh_hash = hash_actor_token("wcbt_ref_old")

    await CBTActorRefreshRecoveryService.store(
        server_id=server_id,
        authorization_id=authorization_id,
        refresh_token_hash=old_refresh_hash,
        idempotency_key=operation_id,
        token_pair=_pair(),
        ttl_seconds=7200,
    )

    key = next(iter(redis.values))
    receipt = json.loads(redis.values[key])
    receipt["ciphertext"] = receipt["ciphertext"][:-4] + "AAAA"
    redis.values[key] = json.dumps(receipt)

    with pytest.raises(CBTRefreshRecoveryUnavailable):
        await CBTActorRefreshRecoveryService.recover(
            server_id=server_id,
            authorization_id=authorization_id,
            refresh_token_hash=old_refresh_hash,
            idempotency_key=operation_id,
        )
