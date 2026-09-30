from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.bulk_imports.models import ImportResourceType
from app.modules.bulk_imports.router import confirm_bulk_import
from app.modules.classes.router import activate_classroom
from app.modules.subjects.router import activate_subject
from app.modules.subscriptions.payment_integrity import process_paystack_webhook_secure
from app.modules.subscriptions.quota_lock import acquire_resource_quota_lock
from app.modules.subscriptions.router import verify_term_plan_checkout
from app.modules.subscriptions.subscription_enums import PaymentStatus, ResourceLimitCode
from app.modules.superadmin.router import update_tenant_status


@pytest.mark.asyncio
async def test_resource_quota_lock_uses_stable_transaction_advisory_key() -> None:
    tenant_id = uuid.uuid4()
    first_db = AsyncMock()
    second_db = AsyncMock()
    other_resource_db = AsyncMock()

    await acquire_resource_quota_lock(
        first_db,
        tenant_id=tenant_id,
        resource=ResourceLimitCode.STUDENTS,
    )
    await acquire_resource_quota_lock(
        second_db,
        tenant_id=tenant_id,
        resource=ResourceLimitCode.STUDENTS,
    )
    await acquire_resource_quota_lock(
        other_resource_db,
        tenant_id=tenant_id,
        resource=ResourceLimitCode.TEACHERS,
    )

    first_params = first_db.execute.await_args.args[1]
    second_params = second_db.execute.await_args.args[1]
    other_params = other_resource_db.execute.await_args.args[1]

    assert first_params["lock_key"] == second_params["lock_key"]
    assert first_params["lock_key"] != other_params["lock_key"]
    assert "pg_advisory_xact_lock" in str(first_db.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_subscription_webhook_compatibility_delegates_to_shared_engine() -> None:
    db = AsyncMock()
    shared = AsyncMock(side_effect=RuntimeError("Unknown payment reference."))

    with patch(
        "app.modules.subscriptions.payment_integrity.process_shared_paystack_webhook",
        shared,
    ):
        with pytest.raises(RuntimeError, match="Unknown payment reference"):
            await process_paystack_webhook_secure(
                db,
                body=b"{}",
                signature="valid",
            )

    shared.assert_awaited_once()
    assert shared.await_args.kwargs["body"] == b"{}"
    assert shared.await_args.kwargs["signature"] == "valid"
    assert callable(shared.await_args.kwargs["settle_charge"])


@pytest.mark.asyncio
async def test_browser_payment_verification_locks_transaction_before_settlement() -> None:
    tenant_id = uuid.uuid4()
    term_id = uuid.uuid4()
    plan = SimpleNamespace(value="professional")
    transaction = SimpleNamespace(
        tenant_id=tenant_id,
        academic_term_id=term_id,
        plan_code=plan,
        reference="term-ref",
        amount_kobo=35_000,
        currency="NGN",
        reconciliation_required=False,
        status=PaymentStatus.PENDING,
    )
    entitlement = SimpleNamespace()
    verified = SimpleNamespace(raw_payload={"data": {"status": "success"}})
    admin = SimpleNamespace(tenant_id=tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subscriptions.router.lock_payment_transaction",
            new=AsyncMock(return_value=transaction),
        ) as lock_transaction,
        patch(
            "app.modules.subscriptions.router.PaymentEngine.verify_transaction",
            new=AsyncMock(return_value=verified),
        ) as verify_provider,
        patch(
            "app.modules.subscriptions.router.settle_verified_term_payment",
            new=AsyncMock(return_value=entitlement),
        ) as settle,
        patch(
            "app.modules.subscriptions.router.TermEntitlementResponse.model_validate",
            return_value=entitlement,
        ),
    ):
        result = await verify_term_plan_checkout(
            reference="term-ref",
            db=db,
            current_admin=admin,
        )

    assert result is entitlement
    lock_transaction.assert_awaited_once_with(db, "term-ref")
    verify_provider.assert_awaited_once_with(
        reference="term-ref",
        expected_amount_kobo=35_000,
        expected_currency="NGN",
        expected_metadata={
            "payment_purpose": "term_subscription",
            "tenant_id": str(tenant_id),
            "academic_term_id": str(term_id),
            "plan_code": "professional",
        },
    )
    settle.assert_awaited_once_with(db, transaction, verified.raw_payload)


@pytest.mark.asyncio
async def test_tenant_status_change_invalidates_active_tenant_authorization_cache() -> None:
    tenant_id = uuid.uuid4()
    tenant = SimpleNamespace(id=tenant_id)
    payload = SimpleNamespace(status="inactive")
    db = AsyncMock()

    with (
        patch(
            "app.modules.superadmin.router.SuperadminService.update_tenant_status",
            new=AsyncMock(return_value=tenant),
        ) as update_status,
        patch(
            "app.modules.superadmin.router._invalidate_tenant_authorization_cache",
            new=AsyncMock(),
        ) as invalidate_auth,
    ):
        result = await update_tenant_status(
            tenant_id=tenant_id,
            payload=payload,
            db=db,
            current_superadmin=SimpleNamespace(),
        )

    assert result is tenant
    update_status.assert_awaited_once_with(db, tenant_id, payload)
    invalidate_auth.assert_awaited_once_with(tenant_id)


@pytest.mark.asyncio
async def test_class_reactivation_has_no_commercial_quota() -> None:
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    payload = SimpleNamespace(confirmation=True)
    activated = SimpleNamespace(id=class_id, is_active=True)

    with patch(
        "app.modules.classes.router.ClassRoomService.activate_classroom",
        new=AsyncMock(return_value=activated),
    ) as activate:
        result = await activate_classroom(
            class_id=class_id,
            payload=payload,
            db=AsyncMock(),
            current_user=actor,
        )

    assert result is activated
    activate.assert_awaited_once()


@pytest.mark.asyncio
async def test_subject_reactivation_has_no_commercial_quota() -> None:
    tenant_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    payload = SimpleNamespace(confirmation=True)

    with patch(
        "app.modules.subjects.router.SubjectService.activate_subject",
        new=AsyncMock(return_value=SimpleNamespace(id=subject_id)),
    ) as activate:
        await activate_subject(
            subject_id=subject_id,
            payload=payload,
            db=AsyncMock(),
            current_user=actor,
        )

    activate.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulk_import_confirmation_locks_resource_before_existing_quota_check() -> None:
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    import_job = SimpleNamespace(resource_type=ImportResourceType.STUDENTS)
    expected = SimpleNamespace(id=job_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.bulk_imports.router.ImportJobRepository.get_job_by_id",
            new=AsyncMock(return_value=import_job),
        ),
        patch(
            "app.modules.bulk_imports.router.acquire_resource_quota_lock",
            new=AsyncMock(),
        ) as quota_lock,
        patch(
            "app.modules.bulk_imports.router.BulkImportLiveService.queue_confirmed_import",
            new=AsyncMock(return_value=expected),
        ) as queue_import,
    ):
        result = await confirm_bulk_import(
            job_id=job_id,
            db=db,
            current_user=actor,
            notify_on_completion=True,
        )

    assert result is expected
    quota_lock.assert_awaited_once_with(
        db,
        tenant_id=tenant_id,
        resource=ResourceLimitCode.STUDENTS,
    )
    queue_import.assert_awaited_once()
