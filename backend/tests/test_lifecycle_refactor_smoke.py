"""Fast smoke tests for the account/membership lifecycle refactor."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.auth.models import AuthSessionActorType
from app.modules.auth.session_service import AuthenticatedActor, AuthSessionService
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.parents.models import Parent, ParentAccount, ParentMembership
from app.modules.student_academics.models import (
    StudentProgressionRunStatus,
)
from app.modules.student_academics.schemas import (
    StudentProgressionRunDetailResponse,
    TeacherAssignmentCreate,
)
from app.modules.students.models import ParentRelationship
from app.modules.students.schemas import StudentCreate
from app.modules.teachers.models import Teacher, TeacherAccount, TeacherMembership


def test_tenant_actor_aliases_point_to_memberships() -> None:
    assert Parent is ParentMembership
    assert Teacher is TeacherMembership
    assert Parent is not ParentAccount
    assert Teacher is not TeacherAccount


def test_auth_identity_global_account_scope_is_explicit() -> None:
    parent_identity = AuthIdentity(
        tenant_id=None,
        identifier="parent@example.com",
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.PARENT_ACCOUNT,
        actor_id=uuid4(),
        is_active=True,
    )
    assert parent_identity.actor_type == ActorType.PARENT_ACCOUNT
    assert parent_identity.tenant_id is None

    teacher_identity = AuthIdentity(
        tenant_id=None,
        identifier="teacher@example.com",
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.TEACHER_ACCOUNT,
        actor_id=uuid4(),
        is_active=True,
    )
    assert teacher_identity.actor_type == ActorType.TEACHER_ACCOUNT
    assert teacher_identity.tenant_id is None


def test_auth_identity_rejects_tenantless_membership_actor() -> None:
    identity = AuthIdentity(
        tenant_id=None,
        identifier="teacher@example.com",
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.TEACHER,
        actor_id=uuid4(),
        is_active=True,
    )
    constraint = next(
        constraint
        for constraint in AuthIdentity.__table__.constraints
        if constraint.name == "ck_auth_identity_actor_scope"
    )
    assert "tenant_id IS NOT NULL" in str(constraint.sqltext)
    assert identity.actor_type == ActorType.TEACHER
    assert identity.tenant_id is None


def test_student_create_rejects_client_owned_identity_fields() -> None:
    with pytest.raises(ValidationError):
        StudentCreate.model_validate(
            {
                "first_name": "Taiwo",
                "last_name": "Student",
                "date_of_birth": "2012-01-01",
                "class_id": str(uuid4()),
                "admission_number": "CLIENT-CONTROLLED",
                "status": "graduated",
            }
        )


def test_student_create_normalizes_parent_email() -> None:
    payload = StudentCreate(
        first_name="Taiwo",
        last_name="Student",
        date_of_birth=date(2012, 1, 1),
        academic_level_id=uuid4(),
        class_id=uuid4(),
        parents=[
            {
                "email": "  PARENT@EXAMPLE.COM ",
                "relationship_type": ParentRelationship.GUARDIAN,
            }
        ],
    )
    assert payload.parents[0].email == "parent@example.com"


def test_teacher_assignment_contract_uses_membership_id() -> None:
    membership_id = uuid4()
    payload = TeacherAssignmentCreate(
        teacher_membership_id=membership_id,
        class_id=uuid4(),
        curriculum_subject_id=uuid4(),
        academic_term_id=uuid4(),
    )
    assert payload.teacher_membership_id == membership_id

    with pytest.raises(ValidationError):
        TeacherAssignmentCreate.model_validate(
            {
                "teacher_id": str(uuid4()),
                "class_id": str(uuid4()),
                "curriculum_subject_id": str(uuid4()),
                "academic_term_id": str(uuid4()),
            }
        )


def test_progression_detail_defaults_to_empty_items() -> None:
    now = datetime.now(timezone.utc)
    response = StudentProgressionRunDetailResponse(
        id=uuid4(),
        tenant_id=uuid4(),
        academic_session_id=uuid4(),
        next_academic_session_id=uuid4(),
        idempotency_key="close-session-2026-0001",
        status=StudentProgressionRunStatus.COMPLETED,
        total_students=0,
        promoted_students=0,
        graduated_students=0,
        skipped_students=0,
        pending_students=0,
        failed_students=0,
        started_at=now,
        completed_at=now,
        initiated_by_admin_id=uuid4(),
        items=[],
        created_at=now,
        updated_at=now,
    )
    assert response.items == []


def test_access_token_claims_preserve_account_and_membership_types() -> None:
    tenant_id = uuid4()
    membership_id = uuid4()
    actor = AuthenticatedActor(
        actor_type=AuthSessionActorType.TEACHER.value,
        account_type=AuthSessionActorType.TEACHER_ACCOUNT.value,
        actor_id=membership_id,
        email="teacher@example.com",
        role="teacher",
        tenant_id=tenant_id,
    )

    claims = AuthSessionService._claims_from_actor(actor)

    assert claims["sub"] == str(membership_id)
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["actor_type"] == "teacher"
    assert claims["account_type"] == "teacher_account"
