from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec
from uuid import uuid4

import pytest

from app.modules.cbt.ai.authoring.schemas import AISingleChoiceQuestionDraft
from app.modules.cbt.ai.authoring.service import AuthoredQuestion, QuestionAuthoringService
from app.modules.cbt.ai.idempotency.cache import AIReplayCache
from app.modules.cbt.ai.idempotency.service import CBTAIIdempotentAuthoringService
from app.modules.cbt.ai.quota.schemas import AICreditSettlementResponse
from app.modules.cbt.ai.quota.service import AIQuotaService
from app.modules.cbt.ai.schemas import AIGenerateQuestionsRequest, AIRegenerateQuestionRequest
from app.modules.cbt.ai.service import CBTAIService
from app.modules.cbt.auth.schemas import AuthenticatedCBTActor


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["generate", "regenerate"])
async def test_new_operation_uses_current_authoring_contract(monkeypatch, operation):
    actor = AuthenticatedCBTActor(
        authorization_id=uuid4(),
        tenant_id=uuid4(),
        actor_id=uuid4(),
        membership_id=uuid4(),
        role="teacher",
    )
    question = AISingleChoiceQuestionDraft(
        question_type="single_choice",
        prompt="What is 2 + 2?",
        options=[{"text": "4", "is_correct": True}, {"text": "5", "is_correct": False}],
    )
    common = dict(subject="Mathematics", academic_level="SS2", generation_prompt="Arithmetic")
    if operation == "generate":
        request = AIGenerateQuestionsRequest(
            **common, question_count=2, question_type_counts={"single_choice": 2}
        )
    else:
        request = AIRegenerateQuestionRequest(
            **common, existing_question=question.model_dump(), instruction="Make it clearer"
        )

    # Different test-only costs expose accidental use of the other operation's cost.
    monkeypatch.setattr(CBTAIService, "CREDITS_PER_GENERATED_QUESTION", 3)
    monkeypatch.setattr(CBTAIService, "CREDITS_PER_REGENERATED_QUESTION", 5)
    reserved = 6 if operation == "generate" else 5
    charged = 3 if operation == "generate" else 5
    reservation_id = uuid4()
    reserve = AsyncMock(
        return_value=SimpleNamespace(
            id=reservation_id,
            total_reserved_credits=reserved,
        )
    )
    settle = AsyncMock(
        return_value=AICreditSettlementResponse(
            reservation_id=reservation_id,
            settled_free_credits=charged,
            settled_extra_credits=0,
            total_settled_credits=charged,
            released_credits=reserved - charged,
            settled_at=datetime.now(timezone.utc),
        )
    )
    monkeypatch.setattr(AIQuotaService, "reserve_credits", reserve)
    monkeypatch.setattr(AIQuotaService, "settle_reservation", settle)
    release = AsyncMock()
    monkeypatch.setattr(CBTAIService, "_release_reservation_safely", release)
    service = CBTAIIdempotentAuthoringService
    monkeypatch.setattr(
        service, "_claim", AsyncMock(return_value=(SimpleNamespace(id=uuid4()), True))
    )
    for name in ("_attach_reservation", "_mark_succeeded", "_mark_failed"):
        monkeypatch.setattr(service, name, AsyncMock())
    store = AsyncMock()
    monkeypatch.setattr(AIReplayCache, "store", store)
    monkeypatch.setattr(AIReplayCache, "delete", AsyncMock())

    authoring = create_autospec(QuestionAuthoringService, instance=True)
    authored = AuthoredQuestion(question=question)
    authoring.generate_questions.return_value = SimpleNamespace(
        questions=[authored], repaired=False
    )
    authoring.regenerate_question.return_value = SimpleNamespace(question=authored, repaired=False)
    monkeypatch.setattr(CBTAIService, "_build_authoring_service", staticmethod(lambda: authoring))
    method = service.generate_questions if operation == "generate" else service.regenerate_question
    response = await method(
        AsyncMock(), actor=actor, request=request, idempotency_key="test-operation"
    )

    if operation == "generate":
        authoring.generate_questions.assert_awaited_once_with(
            request=request.model_dump(exclude_none=True),
            expected_count=2,
            expected_type_counts={"single_choice": 2},
        )
        assert response.questions[0].prompt == question.prompt
    else:
        authoring.regenerate_question.assert_awaited_once_with(
            request=request.model_dump(exclude_none=True),
            expected_question_type="single_choice",
            reference_images=[],
        )
        assert response.question.prompt == question.prompt
    assert reserve.await_args.kwargs["credits"] == reserved
    assert reserve.await_args.kwargs["tenant_id"] == actor.tenant_id
    assert settle.await_args.kwargs["actual_credits"] == charged
    assert response.charge.credits_charged == charged
    assert response.charge.credits_released == reserved - charged
    assert store.await_count == 2
    assert store.await_args_list[0].args[1] == response.model_dump(mode="json")
    service._mark_succeeded.assert_awaited_once()
    service._mark_failed.assert_not_awaited()
    release.assert_not_awaited()
