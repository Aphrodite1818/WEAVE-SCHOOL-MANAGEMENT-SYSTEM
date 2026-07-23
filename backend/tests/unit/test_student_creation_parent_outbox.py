from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.auth_identity.service import AuthIdentityService
from app.modules.classes.repository import ClassRoomRepository
from app.modules.email_outbox.models import EmailOutbox
from app.modules.email_outbox.repository import EmailOutboxRepository
from app.modules.email_outbox.service import (
    PARENT_INVITATION_TEMPLATE,
    TEACHER_INVITATION_TEMPLATE,
    EmailOutboxService,
)
from app.modules.student_academics.lifecycle_repository import (
    AcademicSessionLifecycleRepository,
)
from app.modules.students.creation_service import StudentCreationService
from app.modules.students.models import Gender, ParentRelationship
from app.modules.students.repository import (
    StudentEnrollmentRepository,
    StudentRepository,
)
from app.modules.students.schemas import StudentCreate
from app.modules.students.service import (
    ParentInvitationService,
    StudentAccessCodeService,
    StudentService,
)
from app.tenant_management.identifier_service import TenantIdentifierService


@pytest.mark.asyncio
async def test_queue_parent_invitation_email_builds_expected_outbox_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    queued_item = object()
    create_email = AsyncMock(return_value=queued_item)
    monkeypatch.setattr(EmailOutboxRepository, "create_email", create_email)

    result = await EmailOutboxService.queue_parent_invitation_email(
        object(),  # type: ignore[arg-type]
        tenant_id=tenant_id,
        email="Parent@Example.com",
        school_name="Weave Test School",
        student_name="Ada Student",
        invite_link="https://app.example.com/parent-invitations/token",
        metadata_json={
            "source": "student_creation",
            "student_id": str(uuid4()),
        },
    )

    assert result is queued_item
    kwargs = create_email.await_args.kwargs
    assert kwargs["tenant_id"] == tenant_id

    email_data = kwargs["email_data"]
    assert str(email_data.recipient_email).casefold() == "parent@example.com"
    assert email_data.template_name == PARENT_INVITATION_TEMPLATE
    assert email_data.subject == "Join Weave Test School on Weave"
    assert email_data.template_context == {
        "school_name": "Weave Test School",
        "student_name": "Ada Student",
        "invite_link": "https://app.example.com/parent-invitations/token",
    }
    assert email_data.metadata_json["source"] == "student_creation"


@pytest.mark.asyncio
async def test_worker_sends_parent_invitation_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email_item = EmailOutbox(
        tenant_id=uuid4(),
        recipient_email="parent@example.com",
        recipient_name="parent@example.com",
        subject="Join Weave Test School on Weave",
        template_name=PARENT_INVITATION_TEMPLATE,
        template_context={
            "school_name": "Weave Test School",
            "student_name": "Ada Student",
            "invite_link": "https://app.example.com/parent-invitations/token",
        },
        metadata_json={},
    )
    email_item.attempts = 1

    send_email = AsyncMock(return_value=True)
    mark_sent = AsyncMock(return_value=email_item)
    monkeypatch.setattr(
        "app.modules.email_outbox.service.send_email",
        send_email,
    )
    monkeypatch.setattr(EmailOutboxRepository, "mark_sent", mark_sent)

    db = SimpleNamespace(commit=AsyncMock())

    result = await EmailOutboxService.send_claimed_email(
        db,  # type: ignore[arg-type]
        email_item=email_item,
    )

    assert result is True
    body = send_email.await_args.kwargs["body"]
    assert "Ada Student" in body
    assert "Weave Test School" in body
    assert "https://app.example.com/parent-invitations/token" in body
    assert "/assets/logo.svg" in body
    assert "Review invitation" in body
    assert "Before access is granted" in body
    mark_sent.assert_awaited_once_with(db=db, email_item=email_item)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_sends_teacher_invitation_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email_item = EmailOutbox(
        tenant_id=uuid4(),
        recipient_email="teacher@example.com",
        recipient_name="teacher@example.com",
        subject="Join Weave Test School on Weave",
        template_name=TEACHER_INVITATION_TEMPLATE,
        template_context={
            "school_name": "Weave Test School",
            "invite_link": "https://app.example.com/teacher-invitations/token",
        },
        metadata_json={},
    )
    email_item.attempts = 1

    send_email = AsyncMock(return_value=True)
    mark_sent = AsyncMock(return_value=email_item)
    monkeypatch.setattr(
        "app.modules.email_outbox.service.send_email",
        send_email,
    )
    monkeypatch.setattr(EmailOutboxRepository, "mark_sent", mark_sent)

    db = SimpleNamespace(commit=AsyncMock())

    result = await EmailOutboxService.send_claimed_email(
        db,  # type: ignore[arg-type]
        email_item=email_item,
    )

    assert result is True
    body = send_email.await_args.kwargs["body"]
    assert "Weave Test School" in body
    assert "https://app.example.com/teacher-invitations/token" in body
    assert "/assets/logo.svg" in body
    assert "Review invitation" in body
    assert "What happens next" in body
    mark_sent.assert_awaited_once_with(db=db, email_item=email_item)
    db.commit.assert_awaited_once()


class _FakeStudentDetail:
    def __init__(self) -> None:
        self.update: dict[str, object] | None = None

    def model_copy(self, *, update: dict[str, object]) -> "_FakeStudentDetail":
        self.update = update
        return self


@pytest.mark.asyncio
async def test_student_creation_queues_one_parent_email_per_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    admin_id = uuid4()
    class_id = uuid4()
    session_id = uuid4()
    student_id = uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    actor = SimpleNamespace(id=admin_id, tenant_id=tenant_id)
    tenant = SimpleNamespace(school_name="Weave Test School")
    classroom = SimpleNamespace(
        id=class_id,
        name="JSS 1",
        arm="A",
        is_active=True,
    )
    session = SimpleNamespace(id=session_id)
    detail = _FakeStudentDetail()

    payload = StudentCreate(
        first_name="Ada",
        last_name="Student",
        date_of_birth=date(2012, 1, 1),
        class_id=class_id,
        gender=Gender.FEMALE,
        parents=[
            {
                "email": "mother@example.com",
                "relationship_type": ParentRelationship.MOTHER,
            },
            {
                "email": "father@example.com",
                "relationship_type": ParentRelationship.FATHER,
            },
        ],
    )

    monkeypatch.setattr(
        StudentService,
        "_require_tenant_admin",
        lambda _actor: tenant_id,
    )
    monkeypatch.setattr(
        TenantIdentifierService,
        "require_completed_onboarding",
        AsyncMock(return_value=tenant),
    )
    monkeypatch.setattr(
        ClassRoomRepository,
        "get_by_id",
        AsyncMock(return_value=classroom),
    )
    monkeypatch.setattr(
        AcademicSessionLifecycleRepository,
        "get_current_open",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(
        TenantIdentifierService,
        "generate_identifier",
        AsyncMock(return_value="WVS26483912"),
    )

    async def add_student(_db, student):
        student.id = student_id
        return student

    monkeypatch.setattr(StudentRepository, "add", add_student)
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "add",
        AsyncMock(),
    )
    monkeypatch.setattr(
        AuthIdentityService,
        "create_for_actor",
        AsyncMock(),
    )
    monkeypatch.setattr(
        StudentAccessCodeService,
        "_create_code",
        AsyncMock(
            return_value=SimpleNamespace(
                access_code="48391275",
                expires_at=expires_at,
            )
        ),
    )
    monkeypatch.setattr(
        ParentInvitationService,
        "_create_invitation_record",
        AsyncMock(
            side_effect=[
                SimpleNamespace(id=uuid4(), raw_token="mother-token"),
                SimpleNamespace(id=uuid4(), raw_token="father-token"),
            ]
        ),
    )

    queue_parent_email = AsyncMock()
    monkeypatch.setattr(
        EmailOutboxService,
        "queue_parent_invitation_email",
        queue_parent_email,
    )
    monkeypatch.setattr(
        AuthIdentityService,
        "invalidate_after_commit",
        AsyncMock(),
    )
    monkeypatch.setattr(
        AuthIdentityService,
        "discard_pending_invalidations",
        lambda _db: None,
    )
    monkeypatch.setattr(
        StudentService,
        "_build_detail_response",
        AsyncMock(return_value=detail),
    )

    db = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        refresh=AsyncMock(),
    )

    result = await StudentCreationService.create_student_profile(
        db,  # type: ignore[arg-type]
        actor,  # type: ignore[arg-type]
        payload,
    )

    assert result is detail
    assert queue_parent_email.await_count == 2

    first_call = queue_parent_email.await_args_list[0].kwargs
    second_call = queue_parent_email.await_args_list[1].kwargs

    assert first_call["email"] == "mother@example.com"
    assert first_call["student_name"] == "Ada Student"
    assert first_call["invite_link"].endswith(
        "/parent-invitations/mother-token"
    )
    assert first_call["metadata_json"]["source"] == "student_creation"
    assert first_call["metadata_json"]["student_id"] == str(student_id)

    assert second_call["email"] == "father@example.com"
    assert second_call["invite_link"].endswith(
        "/parent-invitations/father-token"
    )
    assert second_call["metadata_json"]["relationship_type"] == "father"

    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()
    assert detail.update == {
        "setup_code": "48391275",
        "access_code_expires_at": expires_at,
    }
