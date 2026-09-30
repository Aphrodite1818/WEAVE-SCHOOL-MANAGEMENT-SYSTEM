from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.modules.payments.webhook import (
    PaymentWebhookSettlementResult,
    process_paystack_webhook_secure,
)


def _db():
    return SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())


@pytest.mark.asyncio
async def test_invalid_webhook_signature_is_rejected_before_database_work(monkeypatch) -> None:
    provider = SimpleNamespace(
        verify_webhook_signature=lambda **_: False,
        parse_webhook_body=lambda _body: {},
    )
    monkeypatch.setattr("app.modules.payments.webhook.PaystackClient", lambda: provider)
    db = _db()

    with pytest.raises(HTTPException) as exc_info:
        await process_paystack_webhook_secure(
            db,
            body=b"{}",
            signature="invalid",
            settle_charge=AsyncMock(),
        )

    assert exc_info.value.status_code == 401
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_processed_webhook_does_not_settle_again(monkeypatch) -> None:
    payload = {
        "event": "charge.success",
        "data": {"id": 123, "reference": "term-ref"},
    }
    provider = SimpleNamespace(
        verify_webhook_signature=lambda **_: True,
        parse_webhook_body=lambda _body: payload,
    )
    processed_event = SimpleNamespace(processed_at=object())
    settle_charge = AsyncMock()
    db = _db()

    monkeypatch.setattr("app.modules.payments.webhook.PaystackClient", lambda: provider)
    monkeypatch.setattr(
        "app.modules.payments.webhook.acquire_webhook_lock",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.modules.payments.webhook.PaymentRepository.get_webhook_event_by_provider",
        AsyncMock(return_value=processed_event),
    )

    result = await process_paystack_webhook_secure(
        db,
        body=b"{}",
        signature="valid",
        settle_charge=settle_charge,
    )

    assert result.duplicate is True
    settle_charge.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_charge_is_settled_once_and_event_marked_processed(monkeypatch) -> None:
    payload = {
        "event": "charge.success",
        "data": {"id": 123, "reference": "ai-credit-ref"},
    }
    provider = SimpleNamespace(
        verify_webhook_signature=lambda **_: True,
        parse_webhook_body=lambda _body: payload,
    )
    event = SimpleNamespace(processed_at=None, payload=payload)
    post_commit = AsyncMock()
    settle_charge = AsyncMock(
        return_value=PaymentWebhookSettlementResult(
            message="AI credits settled.",
            post_commit=post_commit,
        )
    )
    db = _db()

    monkeypatch.setattr("app.modules.payments.webhook.PaystackClient", lambda: provider)
    monkeypatch.setattr("app.modules.payments.webhook.acquire_webhook_lock", AsyncMock())
    monkeypatch.setattr(
        "app.modules.payments.webhook.PaymentRepository.get_webhook_event_by_provider",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.modules.payments.webhook.PaymentRepository.create_webhook_event",
        AsyncMock(return_value=event),
    )
    mark_processed = AsyncMock(return_value=event)
    monkeypatch.setattr(
        "app.modules.payments.webhook.PaymentRepository.mark_webhook_processed",
        mark_processed,
    )
    monkeypatch.setattr(
        "app.modules.payments.webhook.flush_cache_invalidation_events",
        AsyncMock(),
    )

    result = await process_paystack_webhook_secure(
        db,
        body=b"{}",
        signature="valid",
        settle_charge=settle_charge,
    )

    assert result.message == "AI credits settled."
    assert result.duplicate is False
    settle_charge.assert_awaited_once_with(db, payload)
    mark_processed.assert_awaited_once()
    db.commit.assert_awaited_once()
    post_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_settlement_rolls_back_then_records_webhook_failure(monkeypatch) -> None:
    payload = {
        "event": "charge.success",
        "data": {"id": 123, "reference": "unknown"},
    }
    provider = SimpleNamespace(
        verify_webhook_signature=lambda **_: True,
        parse_webhook_body=lambda _body: payload,
    )
    first_event = SimpleNamespace(processed_at=None, payload=payload)
    failed_event = SimpleNamespace(processed_at=None, payload=payload)
    settle_charge = AsyncMock(side_effect=RuntimeError("Unknown payment reference."))
    db = _db()

    monkeypatch.setattr("app.modules.payments.webhook.PaystackClient", lambda: provider)
    monkeypatch.setattr("app.modules.payments.webhook.acquire_webhook_lock", AsyncMock())
    monkeypatch.setattr(
        "app.modules.payments.webhook.PaymentRepository.get_webhook_event_by_provider",
        AsyncMock(side_effect=[None, None]),
    )
    monkeypatch.setattr(
        "app.modules.payments.webhook.PaymentRepository.create_webhook_event",
        AsyncMock(side_effect=[first_event, failed_event]),
    )
    mark_failed = AsyncMock()
    monkeypatch.setattr(
        "app.modules.payments.webhook.PaymentRepository.mark_webhook_failed",
        mark_failed,
    )
    monkeypatch.setattr(
        "app.modules.payments.webhook.flush_cache_invalidation_events",
        AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="Unknown payment reference"):
        await process_paystack_webhook_secure(
            db,
            body=b"{}",
            signature="valid",
            settle_charge=settle_charge,
        )

    db.rollback.assert_awaited_once()
    db.commit.assert_awaited_once()
    mark_failed.assert_awaited_once_with(
        db,
        webhook_event=failed_event,
        error_message="Unknown payment reference.",
    )
