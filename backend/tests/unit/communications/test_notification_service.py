from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.modules.communications.enums import (
    CommunicationActorType,
    NotificationSourceType,
    NotificationStatus,
)
from app.modules.communications.models import NotificationDelivery
from app.modules.communications.notification_service import NotificationService
from app.modules.communications.recipient_resolver import ResolvedRecipient


@pytest.mark.asyncio
async def test_notification_status_mutation_is_recipient_scoped(monkeypatch) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4())
    delivery = NotificationDelivery(
        tenant_id=actor.tenant_id,
        recipient_actor_type=CommunicationActorType.TENANT_ADMIN,
        recipient_actor_id=actor.id,
        source_type=NotificationSourceType.SYSTEM_EVENT,
        source_id=uuid.uuid4(),
        title="Bulk import completed",
        preview="10 rows imported.",
    )

    async def get_notification_for_actor(_db, **kwargs):
        assert kwargs["actor_type"] == CommunicationActorType.TENANT_ADMIN
        assert kwargs["actor_id"] == actor.id
        return delivery

    async def save(_db, row):
        return row

    monkeypatch.setattr(
        "app.modules.communications.notification_service.CommunicationRepository.get_notification_for_actor",
        get_notification_for_actor,
    )
    monkeypatch.setattr(
        "app.modules.communications.notification_service.CommunicationRepository.save",
        save,
    )
    monkeypatch.setattr(
        "app.modules.communications.notification_service.actor_type_for",
        lambda _actor: CommunicationActorType.TENANT_ADMIN,
    )
    monkeypatch.setattr(
        "app.modules.communications.notification_service.actor_tenant_id",
        lambda item: item.tenant_id,
    )

    updated = await NotificationService.update_status(
        None,
        actor=actor,
        notification_id=uuid.uuid4(),
        status=NotificationStatus.ACKNOWLEDGED,
    )

    assert updated.status == NotificationStatus.ACKNOWLEDGED
    assert updated.read_at is not None
    assert updated.acknowledged_at is not None


@pytest.mark.asyncio
async def test_notification_dismissal_does_not_destroy_source(monkeypatch) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4())
    delivery = NotificationDelivery(
        tenant_id=actor.tenant_id,
        recipient_actor_type=CommunicationActorType.TENANT_ADMIN,
        recipient_actor_id=actor.id,
        source_type=NotificationSourceType.NOTICE,
        source_id=uuid.uuid4(),
        title="School update",
        preview="Assembly starts at 8.",
    )

    async def get_notification_for_actor(_db, **_kwargs):
        return delivery

    async def save(_db, row):
        return row

    monkeypatch.setattr(
        "app.modules.communications.notification_service.CommunicationRepository.get_notification_for_actor",
        get_notification_for_actor,
    )
    monkeypatch.setattr(
        "app.modules.communications.notification_service.CommunicationRepository.save",
        save,
    )
    monkeypatch.setattr(
        "app.modules.communications.notification_service.actor_type_for",
        lambda _actor: CommunicationActorType.TENANT_ADMIN,
    )
    monkeypatch.setattr(
        "app.modules.communications.notification_service.actor_tenant_id",
        lambda item: item.tenant_id,
    )

    updated = await NotificationService.update_status(
        None,
        actor=actor,
        notification_id=delivery.id,
        status=NotificationStatus.DISMISSED,
    )

    assert updated.status == NotificationStatus.DISMISSED
    assert updated.dismissed_at is not None
    assert updated.source_id == delivery.source_id


@pytest.mark.asyncio
async def test_system_event_failure_does_not_escape_source_transaction() -> None:
    class NestedTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class FailingDatabase:
        @staticmethod
        def begin_nested():
            return NestedTransaction()

        async def execute(self, _statement):
            raise RuntimeError("notification schema mismatch")

    tenant_id = uuid.uuid4()
    recipient_id = uuid.uuid4()
    deliveries = await NotificationService.deliver_system_event(
        FailingDatabase(),
        recipients=[
            ResolvedRecipient(
                actor_type=CommunicationActorType.TENANT_ADMIN,
                actor_id=recipient_id,
                tenant_id=tenant_id,
                label="Tenant admin",
            )
        ],
        source_type=NotificationSourceType.BULK_IMPORT,
        source_id=uuid.uuid4(),
        title="Bulk import completed",
        preview="The import completed successfully.",
        action_path="/admin/imports/history/job-id",
        tenant_id=tenant_id,
    )

    assert deliveries == []


@pytest.mark.asyncio
async def test_notification_creation_queues_exact_actor_realtime_signal(monkeypatch) -> None:
    recipient_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    queued = []

    class Result:
        @staticmethod
        def scalar_one_or_none():
            return None

    class Database:
        info = {}

        async def execute(self, _statement):
            return Result()

        @staticmethod
        def add(_row):
            return None

        @staticmethod
        async def flush():
            return None

    monkeypatch.setattr(
        "app.modules.communications.notification_service.RealtimePublisher.defer_to_actor",
        lambda _db, **kwargs: queued.append(kwargs),
    )

    deliveries = await NotificationService.deliver(
        Database(),
        recipients=[
            ResolvedRecipient(
                actor_type=CommunicationActorType.TENANT_ADMIN,
                actor_id=recipient_id,
                tenant_id=tenant_id,
                label="Tenant admin",
            )
        ],
        source_type=NotificationSourceType.SYSTEM_EVENT,
        source_id=uuid.uuid4(),
        title="Ready",
        preview="Persisted state changed.",
        action_path=None,
        tenant_id=tenant_id,
    )

    assert len(deliveries) == 1
    assert queued[0]["event_type"] == "notification.created"
    assert queued[0]["actor_type"] == "tenant_admin"
    assert queued[0]["actor_id"] == recipient_id
    assert queued[0]["tenant_id"] == tenant_id
