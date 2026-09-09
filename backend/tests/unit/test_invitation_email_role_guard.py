from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
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
from app.modules.teachers.models import TeacherMembershipStatus
from app.modules.teachers.repository import (
    TeacherAccountRepository,
    TeacherInvitationRepository,
    TeacherMembershipRepository,
)
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


@pytest.mark.asyncio
async def test_teacher_invitation_rejects_usable_same_tenant_membership_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    account = SimpleNamespace(id=uuid4())
    add_invitation = AsyncMock()
    pending_lookup = AsyncMock()
    background_tasks = SimpleNamespace(add_task=Mock())
    monkeypatch.setattr(
        AccountEmailGuard,
        "ensure_available_for_invitation_role",
        AsyncMock(return_value="teacher@example.com"),
    )
    account_lookup = AsyncMock(return_value=account)
    monkeypatch.setattr(TeacherAccountRepository, "get_by_email", account_lookup)
    monkeypatch.setattr(
        TeacherMembershipRepository,
        "get_by_account_and_tenant",
        AsyncMock(return_value=SimpleNamespace(status=TeacherMembershipStatus.ACTIVE)),
    )
    monkeypatch.setattr(TeacherInvitationRepository, "get_pending_for_email", pending_lookup)
    monkeypatch.setattr(TeacherInvitationRepository, "add", add_invitation)

    with pytest.raises(ConflictException) as captured:
        await TeacherInvitationService.create_invitation(
            db=AsyncMock(),
            actor=SimpleNamespace(id=uuid4(), tenant_id=tenant_id),
            payload=TeacherInvitationCreateCommand(
                email="Teacher@Example.com",
                staff_id="TCH-001",
                job_title="Teacher",
                department=None,
                employment_type=None,
            ),
            background_tasks=background_tasks,
        )

    assert captured.value.payload["code"] == "TEACHER_ALREADY_ACTIVE_MEMBER"
    account_lookup.assert_awaited_once()
    assert account_lookup.await_args.args[1] == "teacher@example.com"
    pending_lookup.assert_not_awaited()
    add_invitation.assert_not_awaited()
    background_tasks.add_task.assert_not_called()


@pytest.mark.parametrize(
    "same_tenant_membership",
    [None, SimpleNamespace(status=TeacherMembershipStatus.INACTIVE)],
)
@pytest.mark.asyncio
async def test_teacher_invitation_allows_other_tenant_or_inactive_membership(
    monkeypatch: pytest.MonkeyPatch,
    same_tenant_membership,
) -> None:
    tenant_id = uuid4()
    monkeypatch.setattr(
        AccountEmailGuard,
        "ensure_available_for_invitation_role",
        AsyncMock(return_value="teacher@example.com"),
    )
    monkeypatch.setattr(
        TeacherAccountRepository,
        "get_by_email",
        AsyncMock(return_value=SimpleNamespace(id=uuid4())),
    )
    monkeypatch.setattr(
        TeacherMembershipRepository,
        "get_by_account_and_tenant",
        AsyncMock(return_value=same_tenant_membership),
    )
    monkeypatch.setattr(
        TeacherInvitationRepository,
        "get_pending_for_email",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        TeacherMembershipRepository,
        "staff_id_exists",
        AsyncMock(return_value=False),
    )
    add_invitation = AsyncMock(side_effect=lambda _db, invitation: invitation)
    monkeypatch.setattr(TeacherInvitationRepository, "add", add_invitation)
    monkeypatch.setattr(
        "app.modules.teachers.service.TenantRepository.get_by_id",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherInvitationResponse.model_validate",
        lambda invitation: SimpleNamespace(invited_email=invitation.invited_email),
    )
    db = SimpleNamespace(commit=AsyncMock())

    response = await TeacherInvitationService.create_invitation(
        db=db,
        actor=SimpleNamespace(id=uuid4(), tenant_id=tenant_id),
        payload=TeacherInvitationCreateCommand(
            email="Teacher@Example.com",
            staff_id="TCH-002",
            job_title="Teacher",
            department=None,
            employment_type=None,
        ),
    )

    assert response.invited_email == "teacher@example.com"
    add_invitation.assert_awaited_once()
    db.commit.assert_awaited_once()


class AsyncMockNone:
    async def __call__(self, *args, **kwargs):
        return None


class AsyncMockValue:
    def __init__(self, value):
        self.value = value

    async def __call__(self, *args, **kwargs):
        return self.value
