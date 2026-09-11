from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import AcademicTermStatus
from app.modules.subscriptions.subscription_enums import TermEntitlementStatus
from app.modules.subscriptions.term_entitlement_service import TermPlanEntitlementService
from app.tenant_management.models import SubscriptionPlan


@pytest.mark.asyncio
async def test_open_term_effective_snapshot_uses_entitlement_plan_only_after_open() -> None:
    tenant_id = uuid4()
    term = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        status=AcademicTermStatus.OPEN,
        is_current=True,
    )
    entitlement = SimpleNamespace(
        tenant_id=tenant_id,
        academic_term_id=term.id,
        plan_code=SubscriptionPlan.PROFESSIONAL,
        status=TermEntitlementStatus.ACTIVE,
    )
    tenant = SimpleNamespace(
        plan=SubscriptionPlan.FREE,
        initial_plan_intent=SubscriptionPlan.PROFESSIONAL,
        trial_ends_at=None,
    )
    db = MagicMock()
    db.flush = AsyncMock()

    with patch(
        "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_tenant",
        new=AsyncMock(return_value=tenant),
    ):
        await TermPlanEntitlementService.mark_effective_for_open_term(
            db,
            tenant_id=tenant_id,
            term=term,
            entitlement=entitlement,
        )

    assert tenant.plan == SubscriptionPlan.PROFESSIONAL
    assert tenant.initial_plan_intent is None
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_draft_term_cannot_apply_effective_plan_snapshot() -> None:
    tenant_id = uuid4()
    term = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        status=AcademicTermStatus.DRAFT,
        is_current=False,
    )
    entitlement = SimpleNamespace(
        tenant_id=tenant_id,
        academic_term_id=term.id,
        plan_code=SubscriptionPlan.PROFESSIONAL,
        status=TermEntitlementStatus.ACTIVE,
    )

    with pytest.raises(ConflictException, match="current open term"):
        await TermPlanEntitlementService.mark_effective_for_open_term(
            MagicMock(),
            tenant_id=tenant_id,
            term=term,
            entitlement=entitlement,
        )
