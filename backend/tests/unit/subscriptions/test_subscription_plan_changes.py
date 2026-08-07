from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.subscriptions.plan_change_service import (
    SubscriptionPlanChangeService,
)
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import (
    ResourceLimitCode,
    SubscriptionPlanChangeType,
    SubscriptionStatus,
)
from app.tenant_management.models import SubscriptionPlan


def test_grace_period_keeps_write_access_during_recovery_window() -> None:
    assert SubscriptionFeatureService._is_write_access_allowed(
        SubscriptionStatus.GRACE_PERIOD
    )
    assert not SubscriptionFeatureService._is_write_access_allowed(
        SubscriptionStatus.EXPIRED
    )


@pytest.mark.asyncio
async def test_professional_downgrade_reports_excess_students() -> None:
    tenant_id = uuid.uuid4()
    subscription = SimpleNamespace(
        plan_code=SubscriptionPlan.ENTERPRISE,
        current_period_end=None,
    )
    usage = {
        ResourceLimitCode.STUDENTS: 1300,
        ResourceLimitCode.TEACHERS: 72,
        ResourceLimitCode.PARENTS: 980,
        ResourceLimitCode.CLASSES: 45,
        ResourceLimitCode.SUBJECTS: 80,
    }

    with (
        patch(
            "app.modules.subscriptions.plan_change_service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(return_value=subscription),
        ),
        patch(
            "app.modules.subscriptions.plan_change_service.SubscriptionRepository.get_all_resource_usage",
            new=AsyncMock(return_value=usage),
        ),
    ):
        preview = await SubscriptionPlanChangeService.preview(
            AsyncMock(),
            tenant_id=tenant_id,
            target_plan_code="professional",
        )

    assert preview.change_type == SubscriptionPlanChangeType.DOWNGRADE
    assert preview.eligible is False
    assert len(preview.blockers) == 1
    blocker = preview.blockers[0]
    assert blocker.resource == ResourceLimitCode.STUDENTS
    assert blocker.used == 1300
    assert blocker.limit == 1000
    assert blocker.excess == 300


@pytest.mark.asyncio
async def test_pending_downgrade_applies_target_limit_to_new_writes() -> None:
    tenant_id = uuid.uuid4()
    pending = SimpleNamespace(
        change_type=SubscriptionPlanChangeType.DOWNGRADE,
        target_plan_code=SubscriptionPlan.PROFESSIONAL,
    )

    with patch(
        "app.modules.subscriptions.plan_change_service.SubscriptionRepository.get_open_plan_change",
        new=AsyncMock(return_value=pending),
    ):
        effective = await SubscriptionPlanChangeService.effective_resource_limit(
            AsyncMock(),
            tenant_id=tenant_id,
            resource=ResourceLimitCode.STUDENTS,
            current_limit=None,
        )

    assert effective == 1000


@pytest.mark.asyncio
async def test_no_pending_downgrade_preserves_unlimited_limit() -> None:
    with patch(
        "app.modules.subscriptions.plan_change_service.SubscriptionRepository.get_open_plan_change",
        new=AsyncMock(return_value=None),
    ):
        effective = await SubscriptionPlanChangeService.effective_resource_limit(
            AsyncMock(),
            tenant_id=uuid.uuid4(),
            resource=ResourceLimitCode.STUDENTS,
            current_limit=None,
        )

    assert effective is None
