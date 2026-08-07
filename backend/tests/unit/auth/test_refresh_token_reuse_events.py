"""Tests for append-only refresh-token reuse attempt recording."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.modules.auth.models import AuthRefreshTokenReuseEvent
from app.modules.auth.repository import AuthRefreshTokenRepository


@pytest.mark.asyncio
async def test_each_reuse_attempt_appends_a_new_event() -> None:
    db = SimpleNamespace(add=Mock(), flush=AsyncMock())
    token = SimpleNamespace(
        id=uuid4(),
        session_id=uuid4(),
        reuse_detected_at=None,
    )
    detected_at = datetime.now(timezone.utc)

    first = await AuthRefreshTokenRepository.mark_reuse_detected(
        db, token, detected_at=detected_at
    )
    second = await AuthRefreshTokenRepository.mark_reuse_detected(
        db, token, detected_at=detected_at
    )

    assert isinstance(first, AuthRefreshTokenReuseEvent)
    assert isinstance(second, AuthRefreshTokenReuseEvent)
    assert first is not second
    assert first.refresh_token_id == second.refresh_token_id == token.id
    assert token.reuse_detected_at == detected_at
    assert db.add.call_count == 2
    assert db.flush.await_count == 2


@pytest.mark.asyncio
async def test_different_tokens_also_append_independent_events() -> None:
    db = SimpleNamespace(add=Mock(), flush=AsyncMock())
    detected_at = datetime.now(timezone.utc)
    first_token = SimpleNamespace(
        id=uuid4(), session_id=uuid4(), reuse_detected_at=None
    )
    second_token = SimpleNamespace(
        id=uuid4(), session_id=uuid4(), reuse_detected_at=None
    )

    first = await AuthRefreshTokenRepository.mark_reuse_detected(
        db, first_token, detected_at=detected_at
    )
    second = await AuthRefreshTokenRepository.mark_reuse_detected(
        db, second_token, detected_at=detected_at
    )

    assert first.refresh_token_id == first_token.id
    assert second.refresh_token_id == second_token.id
    assert first.refresh_token_id != second.refresh_token_id
