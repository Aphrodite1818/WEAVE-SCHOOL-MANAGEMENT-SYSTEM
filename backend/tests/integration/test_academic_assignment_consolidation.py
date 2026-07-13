from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import create_access_token, hash_password
from app.core.dependencies.db import get_db
from app.main import app
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.report_cards.models import ReportCard
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicTerm,
    AcademicTermName,
    ClassSubject,
    ClassSubjectTeacher,
    GradingScale,
    StudentSubjectResult,
    TeacherAssignment,
)
from app.modules.students.models import (
    Gender,
    Student,
    StudentAccountStatus,
    StudentParentLink,
    ParentRelationship,
    StudentProfileStatus,
)
from app.modules.subjects.models import Subject
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
    return {"Authorization": f"Bearer {create_access_token(data=payload)}"}


async def create_auth_identity(
    db_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    identifier: str,
    identifier_type: IdentifierType,
    actor_type: ActorType,
    actor_id: uuid.UUID,
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


async def create_tenant(db_session: AsyncSession, *, suffix: str) -> Tenant:
    tenant = Tenant(
        school_name=f"Test School {suffix}",
        slug=f"test-school-{suffix}",
        admission_number_prefix=f"WVS{suffix.upper()[:6]}",
        email=f"school-{suffix}@example.com",
        country="Nigeria",
        plan=SubscriptionPlan.FREE,
        status=TenantStatus.ACTIVE,
        verification_status=TenantVerificationStatus.ACTIVE,
        onboarding_completed=True,
        is_deleted=False,
    )
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)
    return tenant


async def create_tenant_admin(db_session: AsyncSession, *, tenant: Tenant, email: str) -> TenantAdmin:
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


async def create_teacher(db_session: AsyncSession, *, tenant: Tenant, email: str, first_name: str, last_name: str) -> Teacher:
    teacher = Teacher(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password("TeacherPass123"),
        first_name=first_name,
        last_name=last_name,
        account_status=TeacherAccountStatus.ACTIVE,
        status=TeacherStatus.ACTIVE,
        is_verified=True,
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


async def create_classroom(db_session: AsyncSession, *, tenant: Tenant, name: str, arm: str) -> ClassRoom:
    classroom = ClassRoom(
        tenant_id=tenant.id,
        name=name,
        arm=arm,
        level="JSS",
        is_active=True,
    )
    db_session.add(classroom)
    await db_session.flush()
    await db_session.refresh(classroom)
    return classroom


async def create_subject(db_session: AsyncSession, *, tenant: Tenant, name: str, code: str) -> Subject:
    subject = Subject(
        tenant_id=tenant.id,
        name=name,
        normalized_name=name.lower(),
        code=code,
        normalized_code=code.lower(),
        description=name,
        is_active=True,
    )
    db_session.add(subject)
    await db_session.flush()
    await db_session.refresh(subject)
    return subject


async def create_student(
    db_session: AsyncSession,
    *,
    tenant: Tenant,
    class_room: ClassRoom,
    admission_number: str,
) -> Student:
    student = Student(
        tenant_id=tenant.id,
        admission_number=admission_number,
        password_hash=hash_password("StudentPass123"),
        first_name="Ada",
        last_name="Student",
        account_status=StudentAccountStatus.ACTIVE,
        is_verified=True,
        is_active=True,
        password_reset_required=False,
        admission_date=date.today(),
        gender=Gender.FEMALE,
        profile_status=StudentProfileStatus.COMPLETE,
        class_id=class_room.id,
        arm=class_room.arm,
        status="active",
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


async def create_parent(db_session: AsyncSession, *, tenant: Tenant, email: str) -> Parent:
    parent = Parent(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password("ParentPass123"),
        first_name="Bola",
        last_name="Parent",
        account_status=ParentAccountStatus.ACTIVE,
        is_verified=True,
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


async def create_session_and_term(db_session: AsyncSession, *, tenant: Tenant) -> tuple[AcademicSession, AcademicTerm]:
    academic_session = AcademicSession(
        tenant_id=tenant.id,
        name="2025/2026",
        start_date=date(2025, 9, 1),
        end_date=date(2026, 7, 31),
        is_current=True,
        is_active=True,
    )
    db_session.add(academic_session)
    await db_session.flush()
    await db_session.refresh(academic_session)

    academic_term = AcademicTerm(
        tenant_id=tenant.id,
        academic_session_id=academic_session.id,
        name=AcademicTermName.FIRST_TERM,
        start_date=date(2025, 9, 1),
        end_date=date(2025, 12, 15),
        is_current=True,
        is_active=True,
    )
    db_session.add(academic_term)
    await db_session.flush()
    await db_session.refresh(academic_term)
    return academic_session, academic_term


async def create_grading_scale(db_session: AsyncSession, *, tenant: Tenant) -> GradingScale:
    scale = GradingScale(
        tenant_id=tenant.id,
        min_score=0,
        max_score=100,
        grade="A",
        remark="Excellent",
        is_active=True,
    )
    db_session.add(scale)
    await db_session.flush()
    await db_session.refresh(scale)
    return scale


async def create_class_subject(
    db_session: AsyncSession,
    *,
    tenant: Tenant,
    class_room: ClassRoom,
    subject: Subject,
) -> ClassSubject:
    class_subject = ClassSubject(
        tenant_id=tenant.id,
        class_id=class_room.id,
        subject_id=subject.id,
        is_core=True,
        is_active=True,
    )
    db_session.add(class_subject)
    await db_session.flush()
    await db_session.refresh(class_subject)
    return class_subject


@pytest.mark.asyncio
async def test_teacher_assignment_reassignment_stays_canonical(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tenant = await create_tenant(db_session, suffix="consistency")
    admin = await create_tenant_admin(db_session, tenant=tenant, email="admin-consistency@example.com")
    teacher_a = await create_teacher(
        db_session,
        tenant=tenant,
        email="teacher-a@example.com",
        first_name="Teacher",
        last_name="Alpha",
    )
    teacher_b = await create_teacher(
        db_session,
        tenant=tenant,
        email="teacher-b@example.com",
        first_name="Teacher",
        last_name="Beta",
    )
    classroom = await create_classroom(db_session, tenant=tenant, name="JSS 1", arm="A")
    subject = await create_subject(db_session, tenant=tenant, name="Mathematics", code="MTH")
    class_subject = await create_class_subject(db_session, tenant=tenant, class_room=classroom, subject=subject)
    student = await create_student(
        db_session,
        tenant=tenant,
        class_room=classroom,
        admission_number=f"{tenant.admission_number_prefix}-001",
    )
    parent = await create_parent(db_session, tenant=tenant, email="parent-consistency@example.com")
    db_session.add(
        StudentParentLink(
            tenant_id=tenant.id,
            student_id=student.id,
            parent_id=parent.id,
            relationship_type=ParentRelationship.GUARDIAN,
            is_primary_contact=True,
            receives_academic_updates=True,
            receives_fee_updates=True,
        )
    )
    await create_session_and_term(db_session, tenant=tenant)
    academic_session = (await db_session.execute(select(AcademicSession).where(AcademicSession.tenant_id == tenant.id))).scalar_one()
    academic_term = (await db_session.execute(select(AcademicTerm).where(AcademicTerm.tenant_id == tenant.id))).scalar_one()
    await create_grading_scale(db_session, tenant=tenant)
    await db_session.commit()

    admin_headers = auth_headers(
        actor_id=admin.id,
        actor_type="tenant_admin",
        role="admin",
        email=admin.email,
        tenant_id=tenant.id,
    )
    teacher_a_headers = auth_headers(
        actor_id=teacher_a.id,
        actor_type="teacher",
        role="teacher",
        email=teacher_a.email,
        tenant_id=tenant.id,
    )
    teacher_b_headers = auth_headers(
        actor_id=teacher_b.id,
        actor_type="teacher",
        role="teacher",
        email=teacher_b.email,
        tenant_id=tenant.id,
    )
    student_headers = auth_headers(
        actor_id=student.id,
        actor_type="student",
        role="student",
        email=student.admission_number,
        tenant_id=tenant.id,
    )
    parent_headers = auth_headers(
        actor_id=parent.id,
        actor_type="parent",
        role="parent",
        email=parent.email,
        tenant_id=tenant.id,
    )

    create_response = await api_client.post(
        "/api/v1/tenant-admin/academic/teacher-assignments",
        json={
            "class_subject_id": str(class_subject.id),
            "teacher_id": str(teacher_a.id),
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 201
    created_assignment = create_response.json()
    assignment_a_id = created_assignment["id"]
    assert created_assignment["teacher_id"] == str(teacher_a.id)

    teacher_a_assignments = await api_client.get(
        "/api/v1/teachers/me/academic/assignments",
        headers=teacher_a_headers,
    )
    assert teacher_a_assignments.status_code == 200
    assert len(teacher_a_assignments.json()["items"]) == 1
    assert teacher_a_assignments.json()["items"][0]["teacher_id"] == str(teacher_a.id)

    reassign_response = await api_client.post(
        f"/api/v1/tenant-admin/academic/teacher-assignments/{assignment_a_id}/reassign",
        json={"teacher_id": str(teacher_b.id)},
        headers=admin_headers,
    )
    assert reassign_response.status_code == 200
    reassigned_assignment = reassign_response.json()
    assignment_b_id = reassigned_assignment["id"]
    assert reassigned_assignment["teacher_id"] == str(teacher_b.id)
    assert reassigned_assignment["is_active"] is True

    teacher_a_assignments = await api_client.get(
        "/api/v1/teachers/me/academic/assignments",
        headers=teacher_a_headers,
    )
    assert teacher_a_assignments.status_code == 200
    assert teacher_a_assignments.json()["items"] == []

    teacher_b_assignments = await api_client.get(
        "/api/v1/teachers/me/academic/assignments",
        headers=teacher_b_headers,
    )
    assert teacher_b_assignments.status_code == 200
    teacher_b_items = teacher_b_assignments.json()["items"]
    assert len(teacher_b_items) == 1
    assert teacher_b_items[0]["teacher_id"] == str(teacher_b.id)

    admin_assignments = await api_client.get(
        "/api/v1/tenant-admin/academic/teacher-assignments",
        params={"active_only": "true"},
        headers=admin_headers,
    )
    assert admin_assignments.status_code == 200
    admin_items = admin_assignments.json()["items"]
    assert len(admin_items) == 1
    assert admin_items[0]["teacher_id"] == str(teacher_b.id)

    result_response = await api_client.post(
        "/api/v1/teachers/me/academic/results",
        json={
            "student_id": str(student.id),
            "teacher_assignment_id": str(assignment_b_id),
            "academic_session_id": str(academic_session.id),
            "academic_term_id": str(academic_term.id),
            "test_score": "30",
            "assessment_score": "30",
            "exam_score": "30",
            "status": "submitted",
        },
        headers=teacher_b_headers,
    )
    assert result_response.status_code == 200
    result_payload = result_response.json()
    assert result_payload["teacher_id"] == str(teacher_b.id)
    assert result_payload["teacher_name"] == "Teacher Beta"
    assert result_payload["teacher_assignment_id"] == assignment_b_id

    report_card_response = await api_client.post(
        "/api/v1/tenant-admin/academic/report-cards/generate",
        json={
            "student_id": str(student.id),
            "academic_session_id": str(academic_session.id),
            "academic_term_id": str(academic_term.id),
        },
        headers=admin_headers,
    )
    assert report_card_response.status_code == 201
    report_card_payload = report_card_response.json()
    assert report_card_payload["lines"][0]["teacher_name"] == "Teacher Beta"

    student_results = await api_client.get(
        "/api/v1/students/me/academic/results",
        headers=student_headers,
    )
    assert student_results.status_code == 200
    student_result_items = student_results.json()["items"]
    assert len(student_result_items) == 1
    assert student_result_items[0]["teacher_name"] == "Teacher Beta"

    parent_results = await api_client.get(
        f"/api/v1/parents/me/children/{student.id}/academic/results",
        headers=parent_headers,
    )
    assert parent_results.status_code == 200
    parent_result_items = parent_results.json()["items"]
    assert len(parent_result_items) == 1
    assert parent_result_items[0]["teacher_name"] == "Teacher Beta"

    student_cards = await api_client.get(
        "/api/v1/students/me/academic/report-cards",
        headers=student_headers,
    )
    assert student_cards.status_code == 200
    assert student_cards.json()["items"][0]["lines"][0]["teacher_name"] == "Teacher Beta"

    parent_cards = await api_client.get(
        f"/api/v1/parents/me/children/{student.id}/academic/report-cards",
        headers=parent_headers,
    )
    assert parent_cards.status_code == 200
    assert parent_cards.json()["items"][0]["lines"][0]["teacher_name"] == "Teacher Beta"

    active_assignment_count = (
        await db_session.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.tenant_id == tenant.id,
                TeacherAssignment.class_subject_id == class_subject.id,
                TeacherAssignment.is_active.is_(True),
            )
        )
    ).scalars().all()
    assert len(active_assignment_count) == 1
    assert active_assignment_count[0].teacher_id == teacher_b.id

    legacy_assignment = (
        await db_session.execute(
            select(ClassSubjectTeacher).where(
                ClassSubjectTeacher.tenant_id == tenant.id,
                ClassSubjectTeacher.class_id == classroom.id,
                ClassSubjectTeacher.subject_id == subject.id,
            )
        )
    ).scalar_one()
    assert legacy_assignment.teacher_id == teacher_b.id
    assert legacy_assignment.is_active is True

    persisted_result = (
        await db_session.execute(
            select(StudentSubjectResult).where(
                StudentSubjectResult.tenant_id == tenant.id,
                StudentSubjectResult.student_id == student.id,
            )
        )
    ).scalar_one()
    assert persisted_result.teacher_assignment_id == uuid.UUID(assignment_b_id)
    assert persisted_result.teacher_id == teacher_b.id
    assert persisted_result.class_subject_teacher_id == legacy_assignment.id

    persisted_cards = (
        await db_session.execute(
            select(ReportCard).where(
                ReportCard.tenant_id == tenant.id,
                ReportCard.student_id == student.id,
            )
        )
    ).scalars().all()
    assert len(persisted_cards) == 1


@pytest.mark.asyncio
async def test_student_subject_cards_show_every_class_subject_and_keep_partial_scores_ungraded(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tenant = await create_tenant(db_session, suffix="subjects")
    admin = await create_tenant_admin(db_session, tenant=tenant, email="admin-subjects@example.com")
    teacher = await create_teacher(
        db_session,
        tenant=tenant,
        email="teacher-subjects@example.com",
        first_name="Teacher",
        last_name="Subject",
    )
    classroom = await create_classroom(db_session, tenant=tenant, name="JSS 2", arm="B")
    subject_math = await create_subject(db_session, tenant=tenant, name="Mathematics", code="MTH")
    subject_english = await create_subject(db_session, tenant=tenant, name="English", code="ENG")
    class_subject_math = await create_class_subject(db_session, tenant=tenant, class_room=classroom, subject=subject_math)
    class_subject_english = await create_class_subject(db_session, tenant=tenant, class_room=classroom, subject=subject_english)
    student = await create_student(
        db_session,
        tenant=tenant,
        class_room=classroom,
        admission_number=f"{tenant.admission_number_prefix}-002",
    )
    await create_session_and_term(db_session, tenant=tenant)
    academic_session = (
        await db_session.execute(
            select(AcademicSession).where(AcademicSession.tenant_id == tenant.id)
        )
    ).scalar_one()
    academic_term = (
        await db_session.execute(select(AcademicTerm).where(AcademicTerm.tenant_id == tenant.id))
    ).scalar_one()
    await create_grading_scale(db_session, tenant=tenant)
    await db_session.commit()

    admin_headers = auth_headers(
        actor_id=admin.id,
        actor_type="tenant_admin",
        role="admin",
        email=admin.email,
        tenant_id=tenant.id,
    )
    teacher_headers = auth_headers(
        actor_id=teacher.id,
        actor_type="teacher",
        role="teacher",
        email=teacher.email,
        tenant_id=tenant.id,
    )
    student_headers = auth_headers(
        actor_id=student.id,
        actor_type="student",
        role="student",
        email=student.admission_number,
        tenant_id=tenant.id,
    )

    math_assignment = await api_client.post(
        "/api/v1/tenant-admin/academic/teacher-assignments",
        json={
            "class_subject_id": str(class_subject_math.id),
            "teacher_id": str(teacher.id),
        },
        headers=admin_headers,
    )
    assert math_assignment.status_code == 201
    english_assignment = await api_client.post(
        "/api/v1/tenant-admin/academic/teacher-assignments",
        json={
            "class_subject_id": str(class_subject_english.id),
            "teacher_id": str(teacher.id),
        },
        headers=admin_headers,
    )
    assert english_assignment.status_code == 201

    partial_result = await api_client.post(
        "/api/v1/teachers/me/academic/results",
        json={
            "student_id": str(student.id),
            "teacher_assignment_id": math_assignment.json()["id"],
            "academic_session_id": str(academic_session.id),
            "academic_term_id": str(academic_term.id),
            "test_score": "18",
            "assessment_score": None,
            "exam_score": None,
            "status": "draft",
        },
        headers=teacher_headers,
    )
    assert partial_result.status_code == 200
    partial_payload = partial_result.json()
    assert partial_payload["grade"] is None
    assert float(partial_payload["test_score"]) == 18.0
    assert partial_payload["assessment_score"] is None
    assert partial_payload["exam_score"] is None

    rejected_submit = await api_client.post(
        "/api/v1/teachers/me/academic/results",
        json={
            "student_id": str(student.id),
            "teacher_assignment_id": math_assignment.json()["id"],
            "academic_session_id": str(academic_session.id),
            "academic_term_id": str(academic_term.id),
            "test_score": "18",
            "assessment_score": None,
            "exam_score": None,
            "status": "submitted",
        },
        headers=teacher_headers,
    )
    assert rejected_submit.status_code == 422

    student_subjects = await api_client.get(
        "/api/v1/students/me/academic/subjects",
        headers=student_headers,
    )
    assert student_subjects.status_code == 200
    subject_items = student_subjects.json()["items"]
    assert len(subject_items) == 2

    by_subject_code = {item["subject_code"]: item for item in subject_items}
    math_card = by_subject_code["MTH"]
    english_card = by_subject_code["ENG"]

    assert math_card["result_id"] == partial_payload["id"]
    assert float(math_card["test_score"]) == 18.0
    assert float(math_card["assessment_score"]) == 0.0
    assert float(math_card["exam_score"]) == 0.0
    assert math_card["grade"] is None
    assert math_card["status"] == "draft"

    assert english_card["result_id"] is None
    assert float(english_card["test_score"]) == 0.0
    assert float(english_card["assessment_score"]) == 0.0
    assert float(english_card["exam_score"]) == 0.0
    assert english_card["grade"] is None
    assert english_card["status"] == "pending"

    student_results = await api_client.get(
        "/api/v1/students/me/academic/results",
        headers=student_headers,
    )
    assert student_results.status_code == 200
    result_items = student_results.json()["items"]
    assert len(result_items) == 1
    assert result_items[0]["grade"] is None
    assert float(result_items[0]["total_score"]) == 18.0
