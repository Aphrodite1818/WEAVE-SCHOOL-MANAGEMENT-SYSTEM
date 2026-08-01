from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.auth.account_email_guard import AccountEmailGuard
from app.modules.auth_identity.models import ActorType
from app.modules.auth_identity.repository import AuthIdentityRepository
from app.modules.parents.models import ParentRelationship
from app.modules.parents.repository import ParentInvitationRepository
from app.modules.parents.schemas import ParentInvitationCreateRequest
from app.modules.parents.service import ParentInvitationService
from app.modules.superadmin.repository import SuperAdminRepository
from app.modules.students.repository import StudentRepository
from app.modules.teachers.repository import TeacherInvitationRepository
from app.modules.teachers.service import (
    TeacherInvitationCreateCommand,
    TeacherInvitationService,
)


@pytest.mark.asyncio
async def test_parent_invitation_email_allows_existing_parent_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SuperAdminRepository,
        "get_by_email",
        AsyncMockNone(),
    )
    monkeypatch.setattr(
        AuthIdentityRepository,
        "get_by_identifier",
        AsyncMockValue(SimpleNamespace(actor_type=ActorType.PARENT_ACCOUNT)),
    )

    normalized_email = await AccountEmailGuard.ensure_available_for_invitation_role(
        db=object(),  # type: ignore[arg-type]
        email="Parent@Example.com",
        invited_actor_type=ActorType.PARENT_ACCOUNT,
    )

    assert normalized_email == "parent@example.com"


@pytest.mark.asyncio
async def test_parent_invitation_email_rejects_existing_teacher_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SuperAdminRepository,
        "get_by_email",
        AsyncMockNone(),
    )
    monkeypatch.setattr(
        AuthIdentityRepository,
        "get_by_identifier",
        AsyncMockValue(SimpleNamespace(actor_type=ActorType.TEACHER_ACCOUNT)),
    )

    with pytest.raises(
        ConflictException,
        match="already registered under another role",
    ):
        await AccountEmailGuard.ensure_available_for_invitation_role(
            db=object(),  # type: ignore[arg-type]
            email="teacher@example.com",
            invited_actor_type=ActorType.PARENT_ACCOUNT,
        )


@pytest.mark.asyncio
async def test_teacher_invitation_email_rejects_existing_admin_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SuperAdminRepository,
        "get_by_email",
        AsyncMockNone(),
    )
    monkeypatch.setattr(
        AuthIdentityRepository,
        "get_by_identifier",
        AsyncMockValue(SimpleNamespace(actor_type=ActorType.TENANT_ADMIN)),
    )

    with pytest.raises(
        ConflictException,
        match="already registered under another role",
    ):
        await AccountEmailGuard.ensure_available_for_invitation_role(
            db=object(),  # type: ignore[arg-type]
            email="admin@example.com",
            invited_actor_type=ActorType.TEACHER_ACCOUNT,
        )


@pytest.mark.asyncio
async def test_invitation_email_rejects_superadmin_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        SuperAdminRepository,
        "get_by_email",
        AsyncMockValue(object()),
    )

    with pytest.raises(
        ConflictException,
        match="already registered under another role",
    ):
        await AccountEmailGuard.ensure_available_for_invitation_role(
            db=object(),  # type: ignore[arg-type]
            email="owner@example.com",
            invited_actor_type=ActorType.TEACHER_ACCOUNT,
        )


@pytest.mark.asyncio
async def test_parent_invitation_creation_rejects_wrong_role_before_persisting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    student_id = uuid4()
    add_invitation = AsyncMock()
    monkeypatch.setattr(
        StudentRepository,
        "get_by_id",
        AsyncMock(
            return_value=SimpleNamespace(
                id=student_id,
                admission_number="WVS-001",
            )
        ),
    )
    monkeypatch.setattr(
        SuperAdminRepository,
        "get_by_email",
        AsyncMockNone(),
    )
    monkeypatch.setattr(
        AuthIdentityRepository,
        "get_by_identifier",
        AsyncMockValue(SimpleNamespace(actor_type=ActorType.TEACHER_ACCOUNT)),
    )
    monkeypatch.setattr(ParentInvitationRepository, "add", add_invitation)

    with pytest.raises(
        ConflictException,
        match="already registered under another role",
    ):
        await ParentInvitationService.create_invitation(
            db=AsyncMock(),
            actor=SimpleNamespace(id=uuid4(), tenant_id=tenant_id),
            payload=ParentInvitationCreateRequest(
                student_id=student_id,
                email="teacher@example.com",
                relationship_type=ParentRelationship.FATHER,
            ),
        )

    add_invitation.assert_not_awaited()


@pytest.mark.asyncio
async def test_teacher_invitation_creation_rejects_wrong_role_before_persisting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_invitation = AsyncMock()
    monkeypatch.setattr(
        SuperAdminRepository,
        "get_by_email",
        AsyncMockNone(),
    )
    monkeypatch.setattr(
        AuthIdentityRepository,
        "get_by_identifier",
        AsyncMockValue(SimpleNamespace(actor_type=ActorType.PARENT_ACCOUNT)),
    )
    monkeypatch.setattr(TeacherInvitationRepository, "add", add_invitation)

    with pytest.raises(
        ConflictException,
        match="already registered under another role",
    ):
        await TeacherInvitationService.create_invitation(
            db=AsyncMock(),
            actor=SimpleNamespace(id=uuid4(), tenant_id=uuid4()),
            payload=TeacherInvitationCreateCommand(
                email="parent@example.com",
                staff_id="TCH-001",
                job_title="Teacher",
                department=None,
                employment_type=None,
            ),
        )

    add_invitation.assert_not_awaited()


class AsyncMockNone:
    async def __call__(self, *args, **kwargs):
        return None


class AsyncMockValue:
    def __init__(self, value):
        self.value = value

    async def __call__(self, *args, **kwargs):
        return self.value
