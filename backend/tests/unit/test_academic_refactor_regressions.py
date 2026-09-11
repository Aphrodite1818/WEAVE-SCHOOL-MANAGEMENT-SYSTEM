from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from app.modules.student_academics.lifecycle_repository import StudentProgressionItemRepository
from app.modules.student_academics.models import (
    StudentProgressionItem,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
)


@pytest.mark.asyncio
async def test_progression_item_retry_updates_existing_logical_item(monkeypatch):
    run_id = uuid.uuid4()
    student_id = uuid.uuid4()
    existing_id = uuid.uuid4()
    existing = SimpleNamespace(
        id=existing_id,
        tenant_id=uuid.uuid4(),
        progression_run_id=run_id,
        student_id=student_id,
        from_enrollment_id=None,
        to_enrollment_id=None,
        from_class_id=None,
        to_class_id=None,
        from_level_id=uuid.uuid4(),
        to_level_id=None,
        action=StudentProgressionItemAction.SKIP,
        status=StudentProgressionItemStatus.BLOCKED,
        reason="first failure",
        processed_at=None,
    )
    monkeypatch.setattr(
        StudentProgressionItemRepository,
        "get_by_run_and_student",
        AsyncMock(return_value=existing),
    )
    db = SimpleNamespace(add=lambda item: None, flush=AsyncMock())
    incoming = StudentProgressionItem(
        tenant_id=existing.tenant_id,
        progression_run_id=run_id,
        student_id=student_id,
        action=StudentProgressionItemAction.PROGRESS,
        status=StudentProgressionItemStatus.COMPLETED,
        from_level_id=uuid.uuid4(),
        reason="retry succeeded",
    )

    saved = await StudentProgressionItemRepository.add(db, incoming)

    assert saved is existing
    assert saved.id == existing_id
    assert saved.status == StudentProgressionItemStatus.COMPLETED
    assert saved.reason == "retry succeeded"
    db.flush.assert_awaited_once()


def test_progression_summary_uses_level_only_states():
    from app.modules.student_academics.session_closure_service import SessionClosureService

    items = [
        SimpleNamespace(
            action=StudentProgressionItemAction.PROGRESS,
            status=StudentProgressionItemStatus.COMPLETED,
        ),
        SimpleNamespace(
            action=StudentProgressionItemAction.COMPLETE,
            status=StudentProgressionItemStatus.COMPLETED,
        ),
        SimpleNamespace(
            action=StudentProgressionItemAction.SKIP,
            status=StudentProgressionItemStatus.CANCELLED,
        ),
        SimpleNamespace(
            action=StudentProgressionItemAction.PROGRESS,
            status=StudentProgressionItemStatus.BLOCKED,
        ),
    ]

    assert SessionClosureService._summarize_progression_items(items) == {
        "promoted": 1,
        "graduated": 1,
        "skipped": 1,
        "pending": 0,
        "failed": 1,
    }


def test_current_period_partial_indexes_cover_closing_state():
    from app.modules.student_academics.models import AcademicSession, AcademicTerm

    session_index = next(
        item
        for item in AcademicSession.__table__.indexes
        if item.name == "uq_academic_sessions_current_per_tenant"
    )
    term_index = next(
        item
        for item in AcademicTerm.__table__.indexes
        if item.name == "uq_academic_terms_current_per_tenant"
    )
    assert "closing" in str(session_index.dialect_options["postgresql"]["where"])
    assert "closing" in str(term_index.dialect_options["postgresql"]["where"])


def test_pending_checkout_staleness_boundary():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    from app.modules.subscriptions.subscription_enums import PaymentStatus
    from app.modules.subscriptions.term_entitlement_service import (
        PENDING_CHECKOUT_TTL,
        TermPlanEntitlementService,
    )

    now = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
    fresh = SimpleNamespace(
        status=PaymentStatus.PENDING,
        created_at=now - PENDING_CHECKOUT_TTL + timedelta(seconds=1),
    )
    stale = SimpleNamespace(
        status=PaymentStatus.PENDING,
        created_at=now - PENDING_CHECKOUT_TTL - timedelta(seconds=1),
    )
    assert not TermPlanEntitlementService._pending_checkout_is_stale(fresh, as_of=now)
    assert TermPlanEntitlementService._pending_checkout_is_stale(stale, as_of=now)


def test_subscription_state_tracks_effective_term_entitlement_identity():
    from app.modules.subscriptions.service import ResolvedSubscriptionState
    from app.modules.subscriptions.subscription_enums import (
        BillingInterval,
        PaymentProvider,
        SubscriptionStatus,
    )

    entitlement_id = uuid.uuid4()
    state = ResolvedSubscriptionState(
        tenant_id=uuid.uuid4(),
        plan_code="plus",
        status=SubscriptionStatus.ACTIVE,
        billing_interval=BillingInterval.TERM,
        provider=PaymentProvider.PAYSTACK,
        effective_entitlement_id=entitlement_id,
    )
    from app.modules.subscriptions.service import SubscriptionFeatureService

    response = SubscriptionFeatureService._state_to_subscription_response(state)
    assert response is not None
    assert response.id == entitlement_id
    assert response.plan_code == "plus"


@pytest.mark.asyncio
async def test_academic_write_guard_blocks_current_closing_session():
    from app.core.exceptions import ConflictException
    from app.modules.student_academics.write_guard import ensure_academic_write_window

    closing = SimpleNamespace(id=uuid.uuid4(), name="2026/2027")
    result = SimpleNamespace(first=lambda: closing)
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(ConflictException, match="current session is closing"):
        await ensure_academic_write_window(db, tenant_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_academic_write_guard_allows_non_closing_session():
    from app.modules.student_academics.write_guard import ensure_academic_write_window

    result = SimpleNamespace(first=lambda: None)
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    await ensure_academic_write_window(db, tenant_id=uuid.uuid4())
    assert db.execute.await_count == 2
