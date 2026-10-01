from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.cbt.ai.idempotency.cache import AIReplayCache
from app.modules.cbt.ai.idempotency.models import (
    AI_IDEMPOTENCY_SUCCEEDED,
    AIIdempotencyRecord,
)
from app.modules.cbt.ai.idempotency.service import CBTAIIdempotentAuthoringService
from app.modules.cbt.ai.schemas import AIGenerateQuestionsResponse


def _payload() -> dict:
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
            "reservation_id": str(uuid4()),
            "credits_charged": 1,
            "credits_released": 0,
        },
    }


def _record(request_hash: str) -> AIIdempotencyRecord:
    return AIIdempotencyRecord(
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
async def test_idempotency_key_cannot_be_reused_for_different_request() -> None:
    record = _record("a" * 64)

    with pytest.raises(ConflictException):
        await CBTAIIdempotentAuthoringService._resolve_existing(
            AsyncMock(),
            record=record,
            request_hash="b" * 64,
            response_model=AIGenerateQuestionsResponse,
        )
