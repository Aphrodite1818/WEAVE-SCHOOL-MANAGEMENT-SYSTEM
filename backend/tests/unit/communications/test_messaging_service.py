from __future__ import annotations

import uuid

import pytest

from app.modules.communications.enums import CommunicationActorType
from app.modules.communications.messaging_service import MessagingService
from app.modules.communications.models import Conversation, Message
from app.modules.communications.recipient_resolver import ResolvedRecipient
from app.modules.communications.schemas import ConversationCreate, RecipientTarget
from app.modules.tenant_admins.models import TenantAdmin


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.added_many = []

    def add(self, row) -> None:
        self.added.append(row)

    def add_all(self, rows) -> None:
        self.added_many.extend(rows)

    async def flush(self) -> None:
        return None

    async def refresh(self, _row) -> None:
        return None


@pytest.mark.asyncio
async def test_create_conversation_uses_new_participants_for_first_message(monkeypatch) -> None:
    db = FakeSession()
    tenant_id = uuid.uuid4()
    sender = TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.com",
        password_hash="hash",
    )
    recipient = ResolvedRecipient(
        actor_type=CommunicationActorType.TEACHER,
        actor_id=uuid.uuid4(),
        tenant_id=tenant_id,
        label="Teacher",
    )

    async def find_direct_conversation(*_args, **_kwargs):
        return None

    async def resolve_direct_target(*_args, **_kwargs):
        return recipient

    async def get_conversation_for_actor(_db, **_kwargs):
        return next(row for row in db.added if isinstance(row, Conversation))

    async def deliver(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        "app.modules.communications.messaging_service.CommunicationRepository.find_direct_conversation",
        find_direct_conversation,
    )
    monkeypatch.setattr(
        "app.modules.communications.messaging_service.CommunicationRepository.get_conversation_for_actor",
        get_conversation_for_actor,
    )
    monkeypatch.setattr(
        "app.modules.communications.messaging_service.RecipientResolver.resolve_direct_target",
        resolve_direct_target,
    )
    monkeypatch.setattr(
        "app.modules.communications.messaging_service.NotificationService.deliver",
        deliver,
    )

    payload = ConversationCreate(
        recipient=RecipientTarget(
            actor_type=CommunicationActorType.TEACHER, actor_id=recipient.actor_id
        ),
        body="Hello from admin",
    )

    await MessagingService.create_conversation(db, actor=sender, payload=payload)

    assert any(isinstance(row, Message) for row in db.added)
