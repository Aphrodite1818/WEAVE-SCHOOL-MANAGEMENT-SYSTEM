from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

import pytest

from app.modules.bulk_imports.models import ImportResourceType
from app.modules.bulk_imports.router import confirm_bulk_import
from app.modules.classes.router import activate_classroom
from app.modules.subjects.router import activate_subject
from app.modules.subscriptions.payment_integrity import process_paystack_webhook_secure
from app.modules.subscriptions.quota_lock import acquire_resource_quota_lock
from app.modules.subscriptions.subscription_enums import ResourceLimitCode
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
        resource=ResourceLimitCode.CLASSES,
    )

    first_params = first_db.execute.await_args.args[1]
    second_params = second_db.execute.await_args.args[1]
    other_params = other_resource_db.execute.await_args.args[1]

    assert first_params["lock_key"] == second_params["lock_key"]
    assert first_params["lock_key"] != other_params["lock_key"]
    assert "pg_advisory_xact_lock" in str(first_db.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_failed_paystack_webhook_rolls_back_before_recording_failure() -> None:
    payload = {"event": "charge.success", "data": {"id": 123, "reference": "unknown"}}
    provider = SimpleNamespace(
        verify_webhook_signature=lambda **_: True,
        parse_webhook_body=lambda _body: payload,
    )
    first_event = SimpleNamespace(processed_at=None, payload=payload)
    failure_event = SimpleNamespace(processed_at=None, payload=payload)
    db = SimpleNamespace(rollback=AsyncMock(), commit=AsyncMock())

    with (
        patch(
            "app.modules.subscriptions.payment_integrity.PaystackClient",
            return_value=provider,
        ),
        patch(
            "app.modules.subscriptions.payment_integrity._event_key",
            return_value="charge.success:123",
        ),
        patch(
            "app.modules.subscriptions.payment_integrity._acquire_webhook_lock",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.subscriptions.payment_integrity.SubscriptionRepository.get_webhook_event_by_provider",
            new=AsyncMock(side_effect=[None, None]),
        ),
        patch(
            "app.modules.subscriptions.payment_integrity.SubscriptionRepository.create_webhook_event",
            new=AsyncMock(side_effect=[first_event, failure_event]),
        ) as create_event,
        patch(
            "app.modules.subscriptions.payment_integrity._transaction_for_update",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.subscriptions.payment_integrity.SubscriptionRepository.mark_webhook_failed",
            new=AsyncMock(),
        ) as mark_failed,
        patch(
            "app.modules.subscriptions.payment_integrity.flush_cache_invalidation_events",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(Exception, match="Unknown term payment reference"):
            await process_paystack_webhook_secure(
                db,
                body=b"{}",
                signature="valid",
            )

    db.rollback.assert_awaited_once()
    db.commit.assert_awaited_once()
    assert create_event.await_count == 2
    mark_failed.assert_awaited_once_with(
        db=db,
        webhook_event=failure_event,
        error_message="Unknown term payment reference.",
    )


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
async def test_class_reactivation_checks_quota_only_when_it_increases_usage() -> None:
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    payload = SimpleNamespace(confirmation=True)
    inactive = SimpleNamespace(is_active=False, archived_at=None)
    activated = SimpleNamespace(id=class_id, is_active=True)

    with (
        patch(
            "app.modules.classes.router.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=inactive),
        ),
        patch(
            "app.modules.classes.router.acquire_resource_quota_lock",
            new=AsyncMock(),
        ) as quota_lock,
        patch(
            "app.modules.classes.router.SubscriptionFeatureService.ensure_resource_limit_available",
            new=AsyncMock(),
        ) as quota_check,
        patch(
            "app.modules.classes.router.ClassRoomService.activate_classroom",
            new=AsyncMock(return_value=activated),
        ),
        patch(
            "app.modules.classes.router.SubscriptionFeatureService.invalidate_tenant_subscription_state",
            new=AsyncMock(),
        ),
    ):
        result = await activate_classroom(
            class_id=class_id,
            payload=payload,
            db=AsyncMock(),
            current_user=actor,
        )

    assert result is activated
    quota_lock.assert_awaited_once()
    quota_check.assert_awaited_once()

    with (
        patch(
            "app.modules.classes.router.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=SimpleNamespace(is_active=True, archived_at=None)),
        ),
        patch(
            "app.modules.classes.router.acquire_resource_quota_lock",
            new=AsyncMock(),
        ) as quota_lock,
        patch(
            "app.modules.classes.router.SubscriptionFeatureService.ensure_resource_limit_available",
            new=AsyncMock(),
        ) as quota_check,
        patch(
            "app.modules.classes.router.ClassRoomService.activate_classroom",
            new=AsyncMock(return_value=activated),
        ),
        patch(
            "app.modules.classes.router.SubscriptionFeatureService.invalidate_tenant_subscription_state",
            new=AsyncMock(),
        ),
    ):
        await activate_classroom(
            class_id=class_id,
            payload=payload,
            db=AsyncMock(),
            current_user=actor,
        )

    quota_lock.assert_not_awaited()
    quota_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_subject_reactivation_checks_quota_before_transition() -> None:
    tenant_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    payload = SimpleNamespace(confirmation=True)

    with (
        patch(
            "app.modules.subjects.router.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=SimpleNamespace(is_active=False, archived_at=None)),
        ),
        patch(
            "app.modules.subjects.router.acquire_resource_quota_lock",
            new=AsyncMock(),
        ) as quota_lock,
        patch(
            "app.modules.subjects.router.SubscriptionFeatureService.ensure_resource_limit_available",
            new=AsyncMock(),
        ) as quota_check,
        patch(
            "app.modules.subjects.router.SubjectService.activate_subject",
            new=AsyncMock(return_value=SimpleNamespace(id=subject_id)),
        ),
        patch(
            "app.modules.subjects.router.SubscriptionFeatureService.invalidate_tenant_subscription_state",
            new=AsyncMock(),
        ),
    ):
        await activate_subject(
            subject_id=subject_id,
            payload=payload,
            db=AsyncMock(),
            current_user=actor,
        )

    quota_lock.assert_awaited_once()
    quota_check.assert_awaited_once()


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
