from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import create_access_token, hash_auth_secret, hash_password
from app.config.settings import settings
from app.core.dependencies.db import get_db
from app.main import app
from app.modules.auth.models import AuthPurpose, AuthRecord
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.students.models import (
    Gender,
    Student,
    StudentAccountStatus,
    StudentParentLinkRequest,
    StudentParentLinkRequestStatus,
    StudentProfileStatus,
)
from app.modules.subjects.models import Subject
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher, TeacherAccountStatus, TeacherStatus
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.tenant_management.models import SubscriptionPlan, Tenant, TenantStatus, TenantVerificationStatus


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def create_tenant(
    db_session: AsyncSession,
    *,
    suffix: str,
    status: TenantStatus = TenantStatus.ACTIVE,
    verification_status: TenantVerificationStatus = TenantVerificationStatus.ACTIVE,
    prefix: str = "NHS",
) -> Tenant:
    normalized_suffix = "".join(ch for ch in suffix.upper() if ch.isalnum()) or "TENANT"
    tenant = Tenant(
        school_name=f"Test School {suffix}",
        slug=f"test-school-{suffix.lower()}",
        admission_number_prefix=f"{prefix}{normalized_suffix}"[:20],
        email=f"school-{suffix.lower()}@example.com",
        country="Nigeria",
        plan=SubscriptionPlan.FREE_TRIAL,
        status=status,
        verification_status=verification_status,
        onboarding_completed=True,
        is_deleted=False,
    )
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)
    return tenant


async def create_auth_identity(
    db_session: AsyncSession,
    *,
    tenant_id,
    identifier: str,
    identifier_type: IdentifierType,
    actor_type: ActorType,
    actor_id,
) -> AuthIdentity:
    identity = AuthIdentity(
        tenant_id=tenant_id,
        identifier=identifier,
        identifier_type=identifier_type,
        actor_type=actor_type,
        actor_id=actor_id,
        is_active=True,
    )
    db_session.add(identity)
    await db_session.flush()
    await db_session.refresh(identity)
    return identity


async def create_tenant_admin(
    db_session: AsyncSession,
    *,
    tenant: Tenant,
    email: str = "admin@example.com",
) -> TenantAdmin:
    admin = TenantAdmin(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password("AdminPass123"),
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.flush()
    await db_session.refresh(admin)
    await create_auth_identity(
        db_session,
        tenant_id=tenant.id,
        identifier=email,
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.TENANT_ADMIN,
        actor_id=admin.id,
    )
    return admin


async def create_teacher(
    db_session: AsyncSession,
    *,
    tenant: Tenant,
    email: str,
    verified: bool = True,
    account_status: TeacherAccountStatus = TeacherAccountStatus.ACTIVE,
) -> Teacher:
    teacher = Teacher(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password("TeacherPass123"),
        first_name="Tola",
        last_name="Teacher",
        account_status=account_status,
        status=TeacherStatus.ACTIVE,
        is_verified=verified,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.flush()
    await db_session.refresh(teacher)
    await create_auth_identity(
        db_session,
        tenant_id=tenant.id,
        identifier=email,
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.TEACHER,
        actor_id=teacher.id,
    )
    return teacher


async def create_parent(
    db_session: AsyncSession,
    *,
    tenant: Tenant,
    email: str,
    verified: bool = True,
    account_status: ParentAccountStatus = ParentAccountStatus.ACTIVE,
) -> Parent:
    parent = Parent(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password("ParentPass123"),
        first_name="Bola",
        last_name="Parent",
        account_status=account_status,
        is_verified=verified,
        is_active=True,
    )
    db_session.add(parent)
    await db_session.flush()
    await db_session.refresh(parent)
    await create_auth_identity(
        db_session,
        tenant_id=tenant.id,
        identifier=email,
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.PARENT,
        actor_id=parent.id,
    )
    return parent


async def create_student(
    db_session: AsyncSession,
    *,
    tenant: Tenant,
    admission_number: str,
    password: str = "StudentPass123",
    password_reset_required: bool = False,
) -> Student:
    student = Student(
        tenant_id=tenant.id,
        admission_number=admission_number,
        password_hash=hash_password(password),
        first_name="Ada",
        last_name="Student",
        account_status=StudentAccountStatus.ACTIVE,
        is_verified=True,
        is_active=True,
        password_reset_required=password_reset_required,
        admission_date=datetime.now(timezone.utc).date(),
        status="active",
        profile_status=StudentProfileStatus.COMPLETE,
        gender=Gender.FEMALE,
    )
    db_session.add(student)
    await db_session.flush()
    await db_session.refresh(student)
    await create_auth_identity(
        db_session,
        tenant_id=tenant.id,
        identifier=admission_number,
        identifier_type=IdentifierType.ADMISSION_NUMBER,
        actor_type=ActorType.STUDENT,
        actor_id=student.id,
    )
    return student


async def create_user_invite(
    db_session: AsyncSession,
    *,
    tenant: Tenant,
    email: str,
) -> tuple[AuthRecord, str]:
    raw_token = f"token-{email.replace('@', '-at-')}"
    record = AuthRecord(
        tenant_id=tenant.id,
        email=email,
        hashed_value=hash_auth_secret(raw_token),
        purpose=AuthPurpose.USER_INVITE,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
        is_used=False,
    )
    db_session.add(record)
    await db_session.flush()
    await db_session.refresh(record)
    return record, raw_token


def auth_headers(*, actor_id, actor_type: str, role: str, email: str, tenant_id=None) -> dict[str, str]:
    payload = {
        "sub": str(actor_id),
        "actor_type": actor_type,
        "account_type": actor_type,
        "role": role,
        "email": email,
    }
    if tenant_id is not None:
        payload["tenant_id"] = str(tenant_id)

    token = create_access_token(data=payload)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actor_kind", "email"),
    [
        ("teacher", "teacher@example.com"),
        ("parent", "parent@example.com"),
    ],
)
async def test_accept_invite_returns_success_and_rejects_reuse(
    api_client: AsyncClient,
    db_session: AsyncSession,
    actor_kind: str,
    email: str,
) -> None:
    tenant = await create_tenant(db_session, suffix=actor_kind)

    if actor_kind == "teacher":
        actor = await create_teacher(
            db_session,
            tenant=tenant,
            email=email,
            verified=False,
            account_status=TeacherAccountStatus.PENDING,
        )
    else:
        actor = await create_parent(
            db_session,
            tenant=tenant,
            email=email,
            verified=False,
            account_status=ParentAccountStatus.PENDING,
        )

    invite_record, raw_token = await create_user_invite(
        db_session,
        tenant=tenant,
        email=email,
    )
    await db_session.commit()

    response = await api_client.post(
        "/api/v1/auth/accept-invite",
        json={
            "email": email,
            "password": "InvitePass123",
            "token": raw_token,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["role"] == actor_kind
    assert payload["actor_type"] == actor_kind
    assert payload["account_type"] == actor_kind

    await db_session.refresh(actor)
    await db_session.refresh(invite_record)

    assert invite_record.is_used is True
    assert actor.is_active is True
    assert actor.is_verified is True
    assert actor.last_login_at is not None

    if actor_kind == "teacher":
        assert actor.account_status == TeacherAccountStatus.ACTIVE
    else:
        assert actor.account_status == ParentAccountStatus.ACTIVE

    second_response = await api_client.post(
        "/api/v1/auth/accept-invite",
        json={
            "email": email,
            "password": "InvitePass123",
            "token": raw_token,
        },
    )

    assert second_response.status_code == 400
    assert "already been used" in second_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_student_default_password_first_login_flow(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tenant = await create_tenant(db_session, suffix="student")
    admin = await create_tenant_admin(db_session, tenant=tenant, email="admin-student@example.com")
    await db_session.commit()

    create_response = await api_client.post(
        "/api/v1/tenant-admin/students",
        headers=auth_headers(
            actor_id=admin.id,
            actor_type="tenant_admin",
            role="admin",
            email=admin.email,
            tenant_id=tenant.id,
        ),
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
    )

    assert create_response.status_code == 201
    created_student = create_response.json()
    assert created_student["admission_number"]
    assert created_student["password_reset_required"] is True
    assert created_student["default_password"] == settings.DEFAULT_STUDENT_PASSWORD
    assert "password_hash" not in created_student

    login_response = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": created_student["admission_number"],
            "password": settings.DEFAULT_STUDENT_PASSWORD,
        },
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["access_token"]
    assert login_payload["password_reset_required"] is True
    assert login_payload["user"]["password_reset_required"] is True

    student_headers = {"Authorization": f"Bearer {login_payload['access_token']}"}

    blocked_response = await api_client.get(
        "/api/v1/students/me/parent-links",
        headers=student_headers,
    )
    assert blocked_response.status_code == 403
    assert "change your default password" in blocked_response.json()["detail"].lower()

    change_password_response = await api_client.post(
        "/api/v1/students/me/change-password",
        headers=student_headers,
        json={
            "current_password": settings.DEFAULT_STUDENT_PASSWORD,
            "new_password": "ResetPass123",
            "confirm_password": "ResetPass123",
        },
    )
    assert change_password_response.status_code == 200
    assert change_password_response.json()["password_reset_required"] is False

    onboarding_after_password_response = await api_client.get(
        "/api/v1/students/me/onboarding-status",
        headers=student_headers,
    )
    assert onboarding_after_password_response.status_code == 200
    onboarding_after_password = onboarding_after_password_response.json()
    assert onboarding_after_password["onboarding_required"] is True
    assert onboarding_after_password["current_values"]["password_reset_required"] is False

    complete_profile_response = await api_client.patch(
        "/api/v1/students/me/profile",
        headers=student_headers,
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "date_of_birth": "2012-01-01",
            "gender": "female",
        },
    )
    assert complete_profile_response.status_code == 200
    assert complete_profile_response.json()["profile_status"] == "complete"

    onboarding_complete_response = await api_client.get(
        "/api/v1/students/me/onboarding-status",
        headers=student_headers,
    )
    assert onboarding_complete_response.status_code == 200
    assert onboarding_complete_response.json()["onboarding_required"] is False

    allowed_response = await api_client.get(
        "/api/v1/students/me/parent-links",
        headers=student_headers,
    )
    assert allowed_response.status_code == 200
    assert allowed_response.json()["items"] == []


@pytest.mark.asyncio
async def test_parent_student_link_requests_require_student_approval_and_enforce_tenant_isolation(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tenant_one = await create_tenant(db_session, suffix="tenant1")
    tenant_two = await create_tenant(db_session, suffix="tenant2")

    parent = await create_parent(
        db_session,
        tenant=tenant_one,
        email="parent-link@example.com",
    )
    student = await create_student(
        db_session,
        tenant=tenant_one,
        admission_number="NHS-T1-00001",
        password_reset_required=False,
    )
    other_student = await create_student(
        db_session,
        tenant=tenant_two,
        admission_number="NHS-T2-00001",
        password_reset_required=False,
    )
    await db_session.commit()

    parent_headers = auth_headers(
        actor_id=parent.id,
        actor_type="parent",
        role="parent",
        email=parent.email,
        tenant_id=tenant_one.id,
    )
    student_headers = auth_headers(
        actor_id=student.id,
        actor_type="student",
        role="student",
        email=student.admission_number,
        tenant_id=tenant_one.id,
    )
    other_student_headers = auth_headers(
        actor_id=other_student.id,
        actor_type="student",
        role="student",
        email=other_student.admission_number,
        tenant_id=tenant_two.id,
    )

    request_response = await api_client.post(
        "/api/v1/parents/me/student-link-requests",
        headers=parent_headers,
        json={"admission_number": student.admission_number},
    )
    assert request_response.status_code == 201
    request_payload = request_response.json()
    assert request_payload["status"] == "pending"
    request_id = request_payload["id"]

    duplicate_response = await api_client.post(
        "/api/v1/parents/me/student-link-requests",
        headers=parent_headers,
        json={"admission_number": student.admission_number},
    )
    assert duplicate_response.status_code == 409

    cross_tenant_request_response = await api_client.post(
        "/api/v1/parents/me/student-link-requests",
        headers=parent_headers,
        json={"admission_number": other_student.admission_number},
    )
    assert cross_tenant_request_response.status_code == 404

    parent_list_response = await api_client.get(
        "/api/v1/parents/me/student-link-requests",
        headers=parent_headers,
    )
    assert parent_list_response.status_code == 200
    assert parent_list_response.json()["items"][0]["status"] == "pending"

    student_list_response = await api_client.get(
        "/api/v1/students/me/parent-link-requests",
        headers=student_headers,
    )
    assert student_list_response.status_code == 200
    assert student_list_response.json()["items"][0]["parent"]["email"] == parent.email

    wrong_student_response = await api_client.post(
        f"/api/v1/students/me/parent-link-requests/{request_id}/respond",
        headers=other_student_headers,
        json={"action": "approve"},
    )
    assert wrong_student_response.status_code == 404

    approve_response = await api_client.post(
        f"/api/v1/students/me/parent-link-requests/{request_id}/respond",
        headers=student_headers,
        json={"action": "approve"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    already_processed_response = await api_client.post(
        f"/api/v1/students/me/parent-link-requests/{request_id}/respond",
        headers=student_headers,
        json={"action": "reject"},
    )
    assert already_processed_response.status_code == 400

    linked_students_response = await api_client.get(
        "/api/v1/parents/me/students",
        headers=parent_headers,
    )
    assert linked_students_response.status_code == 200
    assert linked_students_response.json()["items"][0]["student"]["id"] == str(student.id)

    linked_parents_response = await api_client.get(
        "/api/v1/students/me/parent-links",
        headers=student_headers,
    )
    assert linked_parents_response.status_code == 200
    assert linked_parents_response.json()["items"][0]["parent_id"] == str(parent.id)


@pytest.mark.asyncio
async def test_analytics_endpoints_return_real_counts(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    active_tenant = await create_tenant(db_session, suffix="active")
    pending_tenant = await create_tenant(
        db_session,
        suffix="pending",
        status=TenantStatus.INACTIVE,
        verification_status=TenantVerificationStatus.PENDING_VERIFICATION,
    )
    await create_tenant(
        db_session,
        suffix="rejected",
        verification_status=TenantVerificationStatus.REJECTED,
    )
    admin = await create_tenant_admin(db_session, tenant=active_tenant, email="admin-analytics@example.com")
    await create_teacher(db_session, tenant=active_tenant, email="teacher-analytics@example.com")
    await create_parent(db_session, tenant=active_tenant, email="parent-analytics@example.com")
    student = await create_student(
        db_session,
        tenant=active_tenant,
        admission_number="NHS-AN-00001",
        password_reset_required=False,
    )
    student.profile_status = StudentProfileStatus.INCOMPLETE
    student.password_reset_required = True

    db_session.add(
        ClassRoom(
            tenant_id=active_tenant.id,
            name="JSS1",
            arm="A",
        )
    )
    db_session.add(
        Subject(
            tenant_id=active_tenant.id,
            name="Mathematics",
            normalized_name="mathematics",
            code="MTH",
            normalized_code="mth",
            is_active=True,
        )
    )
    db_session.add(
        AuthRecord(
            tenant_id=active_tenant.id,
            email="teacher-analytics@example.com",
            hashed_value=hash_auth_secret("pending-invite-token"),
            purpose=AuthPurpose.USER_INVITE,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            is_used=False,
        )
    )
    db_session.add(
        StudentParentLinkRequest(
            tenant_id=active_tenant.id,
            student_id=student.id,
            parent_id=(await create_parent(
                db_session,
                tenant=active_tenant,
                email="pending-parent@example.com",
                verified=False,
                account_status=ParentAccountStatus.PENDING,
            )).id,
            admission_number_snapshot=student.admission_number,
            status=StudentParentLinkRequestStatus.PENDING,
        )
    )

    superadmin = SuperAdmin(
        email="superadmin@example.com",
        password_hash=hash_password("SuperadminPass123"),
        is_active=True,
    )
    db_session.add(superadmin)
    await db_session.commit()
    await db_session.refresh(superadmin)

    superadmin_response = await api_client.get(
        "/api/v1/superadmin/analytics/overview",
        headers={
            "Authorization": f"Bearer {create_access_token({'sub': str(superadmin.id), 'role': 'superadmin', 'account_type': 'superadmin', 'email': superadmin.email})}"
        },
    )
    assert superadmin_response.status_code == 200
    superadmin_payload = superadmin_response.json()
    assert superadmin_payload["stats"]["total_tenants"] == 3
    assert superadmin_payload["stats"]["active_tenants"] == 1
    assert superadmin_payload["stats"]["pending_verification"] == 1
    assert superadmin_payload["stats"]["rejected_verification"] == 1
    assert superadmin_payload["stats"]["total_tenant_admins"] == 1

    tenant_admin_response = await api_client.get(
        "/api/v1/tenant-admin/analytics/overview",
        headers=auth_headers(
            actor_id=admin.id,
            actor_type="tenant_admin",
            role="admin",
            email=admin.email,
            tenant_id=active_tenant.id,
        ),
    )
    assert tenant_admin_response.status_code == 200
    tenant_payload = tenant_admin_response.json()
    assert tenant_payload["stats"]["total_students"] == 1
    assert tenant_payload["stats"]["total_teachers"] == 1
    assert tenant_payload["stats"]["total_parents"] == 2
    assert tenant_payload["stats"]["total_classes"] == 1
    assert tenant_payload["stats"]["total_subjects"] == 1
    assert tenant_payload["stats"]["pending_user_invites"] == 1
    assert tenant_payload["stats"]["pending_parent_link_requests"] == 1
