from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.cbt.ai.idempotency.cache import AIReplayCache
from app.modules.cbt.ai.idempotency.models import (
    AI_IDEMPOTENCY_IN_PROGRESS,
    AI_IDEMPOTENCY_SUCCEEDED,
    AIIdempotencyRecord,
)
from app.modules.cbt.ai.idempotency.service import CBTAIIdempotentAuthoringService
from app.modules.cbt.ai.quota.models import AICreditReservationStatus
from app.modules.cbt.ai.quota.repository import AICreditReservationRepository
from app.modules.cbt.ai.quota.service import AIQuotaService
from app.modules.cbt.ai.schemas import AIGenerateQuestionsResponse


def _payload(reservation_id=None) -> dict:
    return {
        "questions": [
            {
                "question_type": "single_choice",
                "prompt": "What is 2 + 2?",
                "instruction": None,
                "image": None,
                "options": [
                    {"text": "4", "is_correct": True, "image": None},
                    {"text": "5", "is_correct": False, "image": None},
                ],
            }
        ],
        "repaired": False,
        "charge": {
            "reservation_id": str(reservation_id or uuid4()),
            "credits_charged": 1,
            "credits_released": 0,
        },
    }


def _record(request_hash: str) -> AIIdempotencyRecord:
    return AIIdempotencyRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        actor_type="teacher",
        actor_id=uuid4(),
        operation="generate",
        idempotency_key="operation-1",
        request_hash=request_hash,
        status=AI_IDEMPOTENCY_SUCCEEDED,
    )


@pytest.mark.asyncio
async def test_succeeded_idempotent_request_replays_cached_result_without_execution() -> None:
    record = _record("a" * 64)
    cached = _payload()

    with patch.object(
        AIReplayCache,
        "load",
        new=AsyncMock(return_value=cached),
    ) as load:
        response = await CBTAIIdempotentAuthoringService._resolve_existing(
            AsyncMock(),
            record=record,
            request_hash="a" * 64,
            response_model=AIGenerateQuestionsResponse,
        )

    assert response.questions[0].prompt == "What is 2 + 2?"
    assert response.charge.credits_charged == 1
    load.assert_awaited_once_with(record.id)


@pytest.mark.asyncio
async def test_pending_reservation_with_replay_settles_without_regeneration() -> None:
    record = _record("a" * 64)
    record.status = AI_IDEMPOTENCY_IN_PROGRESS
    reservation_id = uuid4()
    record.reservation_id = reservation_id
    reservation = SimpleNamespace(
        id=reservation_id,
        status=AICreditReservationStatus.PENDING,
    )
    settlement = SimpleNamespace(
        total_settled_credits=1,
        released_credits=0,
    )
    cached = _payload(reservation_id)
    db = AsyncMock()

    with (
        patch.object(
            AICreditReservationRepository,
            "get_by_tenant_and_id",
            new=AsyncMock(return_value=reservation),
        ),
        patch.object(
            CBTAIIdempotentAuthoringService,
            "_load_replay",
            new=AsyncMock(return_value=cached),
        ),
        patch.object(
            AIQuotaService,
            "settle_reservation",
            new=AsyncMock(return_value=settlement),
        ) as settle,
        patch.object(
            CBTAIIdempotentAuthoringService,
            "_mark_succeeded",
            new=AsyncMock(),
        ) as mark_succeeded,
        patch.object(
            AIReplayCache,
            "store",
            new=AsyncMock(),
        ),
    ):
        response = await CBTAIIdempotentAuthoringService._resolve_existing(
            db,
            record=record,
            request_hash="a" * 64,
            response_model=AIGenerateQuestionsResponse,
        )

    assert response.questions[0].prompt == "What is 2 + 2?"
    assert response.charge.reservation_id == reservation_id
    settle.assert_awaited_once_with(
        db,
        tenant_id=record.tenant_id,
        reservation_id=reservation_id,
        actual_credits=1,
    )
    mark_succeeded.assert_awaited_once_with(
        db,
        tenant_id=record.tenant_id,
        record_id=record.id,
        credits_charged=1,
        credits_released=0,
    )


@pytest.mark.asyncio
async def test_idempotency_key_cannot_be_reused_for_different_request() -> None:
    record = _record("a" * 64)

    with pytest.raises(ConflictException):
        await CBTAIIdempotentAuthoringService._resolve_existing(
            AsyncMock(),
            record=record,
            request_hash="b" * 64,
            response_model=AIGenerateQuestionsResponse,
        )
