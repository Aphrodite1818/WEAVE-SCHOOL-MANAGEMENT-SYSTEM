from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.cbt.ai.quota.models import (
    AICreditAllocation,
    AICreditLedger,
    AICreditReservation,
    AIExtraCreditBalance,
    AIQuotaAccount,
    AIQuotaActorType,
    AIQuotaPurchase,
    AIQuotaRequest,
    AITenantCreditBalance,
    AIWeeklyQuota,
)
from app.modules.cbt.ai.quota.schemas import (
    AICreditAllocationCreate,
    AIQuotaRequestApprove,
    AIQuotaRequestCreate,
    AIQuotaRequestReject,
    AIQuotaTopUpRequest,
)


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (AIQuotaRequestCreate, {"credits": 0}),
        (AIQuotaTopUpRequest, {"credits": -1}),
        (
            AICreditAllocationCreate,
            {
                "recipient_actor_type": AIQuotaActorType.TEACHER,
                "recipient_actor_id": uuid4(),
                "credits": 0,
            },
        ),
    ],
)
def test_credit_request_contracts_require_positive_credits(schema, payload) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_quota_schemas_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AIQuotaRequestCreate.model_validate({"credits": 10, "tenant_id": str(uuid4())})


def test_approval_and_rejection_notes_strip_whitespace() -> None:
    approval = AIQuotaRequestApprove(approved_credits=10, note="  approved  ")
    rejection = AIQuotaRequestReject(note="  no reserve  ")
    assert approval.note == "approved"
    assert rejection.note == "no reserve"


def test_allocation_contract_accepts_supported_actor_types() -> None:
    actor_id = uuid4()
    item = AICreditAllocationCreate(
        recipient_actor_type=AIQuotaActorType.TENANT_ADMIN,
        recipient_actor_id=actor_id,
        credits=25,
    )
    assert item.recipient_actor_id == actor_id
    assert item.recipient_actor_type == AIQuotaActorType.TENANT_ADMIN


def test_quota_models_keep_expected_table_contracts() -> None:
    assert AIQuotaAccount.__tablename__ == "cbt_ai_quota_accounts"
    assert AIWeeklyQuota.__tablename__ == "cbt_ai_weekly_quotas"
    assert AIExtraCreditBalance.__tablename__ == "cbt_ai_extra_credit_balances"
    assert AITenantCreditBalance.__tablename__ == "cbt_ai_tenant_credit_balances"
    assert AICreditReservation.__tablename__ == "cbt_ai_credit_reservations"
    assert AICreditAllocation.__tablename__ == "cbt_ai_credit_allocations"
    assert AIQuotaRequest.__tablename__ == "cbt_ai_quota_requests"
    assert AIQuotaPurchase.__tablename__ == "cbt_ai_quota_purchases"
    assert AICreditLedger.__tablename__ == "cbt_ai_credit_ledger"


def test_quota_actor_enum_values_are_stable() -> None:
    assert {item.value for item in AIQuotaActorType} == {"teacher", "tenant_admin"}
