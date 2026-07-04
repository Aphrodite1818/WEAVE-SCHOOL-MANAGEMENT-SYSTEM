from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Select, select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.database import AsyncSessionLocal, engine
from app.config.security import hash_password
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import AuthService
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.student_academics.models import (
    AcademicResultStatus,
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
    AcademicStatus,
    Gender,
    ParentRelationship,
    Student,
    StudentAccountStatus,
    StudentParentLink,
    StudentProfileStatus,
)
from app.modules.subjects.models import Subject
from app.modules.teachers.models import (
    Teacher,
    TeacherAccountStatus,
    TeacherStatus,
    TeacherSubject,
)
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.models import Tenant, TenantStatus, TenantVerificationStatus


DEFAULT_PASSWORD = "Test12345!"


@dataclass(frozen=True)
class TeacherSeed:
    email: str
    first_name: str
    last_name: str
    staff_id: str
    qualification: str
    specialization: str


@dataclass(frozen=True)
class ParentSeed:
    email: str
    first_name: str
    last_name: str
    phone_number: str
    occupation: str


@dataclass(frozen=True)
class ClassSeed:
    key: str
    name: str
    level: str
    arm: str
    homeroom_teacher_email: str


@dataclass(frozen=True)
class StudentSeed:
    admission_number: str
    first_name: str
    last_name: str
    class_key: str
    gender: Gender
    date_of_birth: date
    parent_email: str
    relationship_type: ParentRelationship


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_admission_number(value: str) -> str:
    return value.strip().upper()


def normalize_subject_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def normalize_subject_code(value: str) -> str:
    return value.strip().upper()


async def scalar_one_or_none(session, statement: Select):
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def ensure_auth_identity(
    session,
    *,
    tenant_id: uuid.UUID,
    identifier: str,
    identifier_type: IdentifierType,
    actor_type: ActorType,
    actor_id: uuid.UUID,
) -> AuthIdentity:
    normalized_identifier = (
        normalize_email(identifier)
        if identifier_type == IdentifierType.EMAIL
        else normalize_admission_number(identifier)
    )
    identity = await scalar_one_or_none(
        session,
        select(AuthIdentity).where(
            AuthIdentity.actor_type == actor_type,
            AuthIdentity.actor_id == actor_id,
        ),
    )
    if identity is None:
        identity = await scalar_one_or_none(
            session,
            select(AuthIdentity).where(
                AuthIdentity.identifier_type == identifier_type,
                AuthIdentity.identifier == normalized_identifier,
            ),
        )
    if identity is None:
        identity = AuthIdentity(
            tenant_id=tenant_id,
            identifier=normalized_identifier,
            identifier_type=identifier_type,
            actor_type=actor_type,
            actor_id=actor_id,
            is_active=True,
        )
        session.add(identity)
        await session.flush()
        return identity

    identity.tenant_id = tenant_id
    identity.identifier = normalized_identifier
    identity.identifier_type = identifier_type
    identity.actor_type = actor_type
    identity.actor_id = actor_id
    identity.is_active = True
    await session.flush()
    return identity


async def resolve_first_seed_student_admission_number(session, tenant_id_arg: str | None) -> str:
    tenant = await resolve_target_tenant(session, tenant_id_arg)
    prefix = tenant.admission_number_prefix or "DBS"
    return f"{prefix}2600001"


async def verify_logins(tenant_id_arg: str | None) -> None:
    async with AsyncSessionLocal() as session:
        first_student_admission_number = await resolve_first_seed_student_admission_number(
            session,
            tenant_id_arg,
        )

        teacher_auth = await AuthService.authenticate_actor(
            session,
            LoginRequest(identifier="testteacher1@gmail.com", password=DEFAULT_PASSWORD),
        )
        student_auth = await AuthService.authenticate_actor(
            session,
            LoginRequest(identifier=first_student_admission_number, password=DEFAULT_PASSWORD),
        )
        print(
            "Verified login:",
            f"teacher={teacher_auth.actor_type}",
            f"student={student_auth.actor_type}",
            f"tenant_id={teacher_auth.tenant_id or tenant_id_arg}",
        )


async def resolve_target_tenant(session, tenant_id_arg: str | None) -> Tenant:
    if tenant_id_arg:
        tenant_id = uuid.UUID(tenant_id_arg)
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant {tenant_id} was not found.")
        return tenant

    result = await session.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = list(result.scalars().all())
    if not tenants:
        raise ValueError("No tenants exist in the database.")
    if len(tenants) > 1:
        raise ValueError("Multiple tenants found. Re-run with --tenant-id to avoid seeding the wrong school.")
    return tenants[0]


async def ensure_tenant_ready(session, tenant: Tenant) -> None:
    tenant.verification_status = TenantVerificationStatus.ACTIVE
    if tenant.status not in (TenantStatus.ACTIVE, TenantStatus.TRIAL):
        tenant.status = TenantStatus.TRIAL
    tenant.onboarding_completed = True
    await session.flush()


async def ensure_teacher(
    session,
    *,
    tenant_id: uuid.UUID,
    payload: TeacherSeed,
) -> Teacher:
    email = normalize_email(payload.email)
    teacher = await scalar_one_or_none(
        session,
        select(Teacher).where(
            Teacher.tenant_id == tenant_id,
            Teacher.email == email,
        ),
    )
    if teacher is None:
        teacher = Teacher(
            tenant_id=tenant_id,
            email=email,
            password_hash=hash_password(DEFAULT_PASSWORD),
        )
        session.add(teacher)

    teacher.email = email
    teacher.password_hash = hash_password(DEFAULT_PASSWORD)
    teacher.first_name = payload.first_name
    teacher.last_name = payload.last_name
    teacher.staff_id = payload.staff_id
    teacher.qualification = payload.qualification
    teacher.specialization = payload.specialization
    teacher.account_status = TeacherAccountStatus.ACTIVE
    teacher.status = TeacherStatus.ACTIVE
    teacher.is_verified = True
    teacher.is_active = True
    await session.flush()

    await ensure_auth_identity(
        session,
        tenant_id=tenant_id,
        identifier=email,
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.TEACHER,
        actor_id=teacher.id,
    )
    return teacher


async def ensure_parent(
    session,
    *,
    tenant_id: uuid.UUID,
    payload: ParentSeed,
) -> Parent:
    email = normalize_email(payload.email)
    parent = await scalar_one_or_none(
        session,
        select(Parent).where(
            Parent.tenant_id == tenant_id,
            Parent.email == email,
        ),
    )
    if parent is None:
        parent = Parent(
            tenant_id=tenant_id,
            email=email,
            password_hash=hash_password(DEFAULT_PASSWORD),
        )
        session.add(parent)

    parent.email = email
    parent.password_hash = hash_password(DEFAULT_PASSWORD)
    parent.first_name = payload.first_name
    parent.last_name = payload.last_name
    parent.phone_number = payload.phone_number
    parent.occupation = payload.occupation
    parent.address = "123 Demo Street, Lagos"
    parent.emergency_phone = payload.phone_number
    parent.account_status = ParentAccountStatus.ACTIVE
    parent.is_verified = True
    parent.is_active = True
    await session.flush()

    await ensure_auth_identity(
        session,
        tenant_id=tenant_id,
        identifier=email,
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.PARENT,
        actor_id=parent.id,
    )
    return parent


async def ensure_classroom(
    session,
    *,
    tenant_id: uuid.UUID,
    payload: ClassSeed,
    teacher_id: uuid.UUID,
) -> ClassRoom:
    classroom = await scalar_one_or_none(
        session,
        select(ClassRoom).where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.name == payload.name,
            ClassRoom.arm == payload.arm,
        ),
    )
    if classroom is None:
        classroom = ClassRoom(
            tenant_id=tenant_id,
            name=payload.name,
            arm=payload.arm,
            level=payload.level,
            teacher_id=teacher_id,
            is_active=True,
        )
        session.add(classroom)
    else:
        classroom.level = payload.level
        classroom.teacher_id = teacher_id
        classroom.is_active = True

    await session.flush()
    return classroom


async def ensure_subject(
    session,
    *,
    tenant_id: uuid.UUID,
    name: str,
    code: str,
    description: str,
) -> Subject:
    normalized_name = normalize_subject_name(name)
    subject = await scalar_one_or_none(
        session,
        select(Subject).where(
            Subject.tenant_id == tenant_id,
            Subject.normalized_name == normalized_name,
        ),
    )
    if subject is None:
        subject = Subject(
            tenant_id=tenant_id,
            name=name,
            normalized_name=normalized_name,
            code=normalize_subject_code(code),
            normalized_code=normalize_subject_code(code),
            description=description,
            is_active=True,
        )
        session.add(subject)
    else:
        subject.name = name
        subject.code = normalize_subject_code(code)
        subject.normalized_code = normalize_subject_code(code)
        subject.description = description
        subject.is_active = True

    await session.flush()
    return subject


async def ensure_teacher_subject(
    session,
    *,
    tenant_id: uuid.UUID,
    teacher_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> TeacherSubject:
    link = await scalar_one_or_none(
        session,
        select(TeacherSubject).where(
            TeacherSubject.tenant_id == tenant_id,
            TeacherSubject.teacher_id == teacher_id,
            TeacherSubject.subject_id == subject_id,
        ),
    )
    if link is None:
        link = TeacherSubject(
            tenant_id=tenant_id,
            teacher_id=teacher_id,
            subject_id=subject_id,
        )
        session.add(link)
        await session.flush()
    return link


async def ensure_student(
    session,
    *,
    tenant_id: uuid.UUID,
    payload: StudentSeed,
    classroom: ClassRoom,
) -> Student:
    admission_number = normalize_admission_number(payload.admission_number)
    student = await scalar_one_or_none(
        session,
        select(Student).where(
            Student.tenant_id == tenant_id,
            Student.admission_number == admission_number,
        ),
    )
    if student is None:
        student = Student(
            tenant_id=tenant_id,
            admission_number=admission_number,
            password_hash=hash_password(DEFAULT_PASSWORD),
        )
        session.add(student)

    student.admission_number = admission_number
    student.password_hash = hash_password(DEFAULT_PASSWORD)
    student.first_name = payload.first_name
    student.last_name = payload.last_name
    student.account_status = StudentAccountStatus.ACTIVE
    student.is_verified = True
    student.is_active = True
    student.password_reset_required = False
    student.date_of_birth = payload.date_of_birth
    student.gender = payload.gender
    student.class_id = classroom.id
    student.arm = classroom.arm
    student.status = AcademicStatus.ACTIVE
    student.profile_status = StudentProfileStatus.COMPLETE
    student.admission_date = date(2025, 9, 8)
    await session.flush()

    await ensure_auth_identity(
        session,
        tenant_id=tenant_id,
        identifier=admission_number,
        identifier_type=IdentifierType.ADMISSION_NUMBER,
        actor_type=ActorType.STUDENT,
        actor_id=student.id,
    )
    return student


async def ensure_parent_link(
    session,
    *,
    tenant_id: uuid.UUID,
    student_id: uuid.UUID,
    parent_id: uuid.UUID,
    relationship_type: ParentRelationship,
    is_primary_contact: bool,
) -> StudentParentLink:
    link = await scalar_one_or_none(
        session,
        select(StudentParentLink).where(
            StudentParentLink.tenant_id == tenant_id,
            StudentParentLink.student_id == student_id,
            StudentParentLink.parent_id == parent_id,
        ),
    )
    if link is None:
        link = StudentParentLink(
            tenant_id=tenant_id,
            student_id=student_id,
            parent_id=parent_id,
            relationship_type=relationship_type,
            is_primary_contact=is_primary_contact,
            receives_academic_updates=True,
            receives_fee_updates=True,
        )
        session.add(link)
    else:
        link.relationship_type = relationship_type
        link.is_primary_contact = is_primary_contact
        link.receives_academic_updates = True
        link.receives_fee_updates = True

    await session.flush()
    return link


async def ensure_academic_session(session, *, tenant_id: uuid.UUID) -> AcademicSession:
    academic_session = await scalar_one_or_none(
        session,
        select(AcademicSession).where(
            AcademicSession.tenant_id == tenant_id,
            AcademicSession.name == "2025/2026",
        ),
    )
    if academic_session is None:
        academic_session = AcademicSession(
            tenant_id=tenant_id,
            name="2025/2026",
            start_date=date(2025, 9, 8),
            end_date=date(2026, 7, 31),
            is_current=True,
            is_active=True,
        )
        session.add(academic_session)
    else:
        academic_session.start_date = date(2025, 9, 8)
        academic_session.end_date = date(2026, 7, 31)
        academic_session.is_current = True
        academic_session.is_active = True

    result = await session.execute(
        select(AcademicSession).where(
            AcademicSession.tenant_id == tenant_id,
            AcademicSession.name != "2025/2026",
            AcademicSession.is_current.is_(True),
        )
    )
    for item in result.scalars().all():
        item.is_current = False

    await session.flush()
    return academic_session


async def ensure_academic_term(
    session,
    *,
    tenant_id: uuid.UUID,
    academic_session_id: uuid.UUID,
    name: AcademicTermName,
    start_date_value: date,
    end_date_value: date,
    is_current: bool,
) -> AcademicTerm:
    term = await scalar_one_or_none(
        session,
        select(AcademicTerm).where(
            AcademicTerm.tenant_id == tenant_id,
            AcademicTerm.academic_session_id == academic_session_id,
            AcademicTerm.name == name,
        ),
    )
    if term is None:
        term = AcademicTerm(
            tenant_id=tenant_id,
            academic_session_id=academic_session_id,
            name=name,
            start_date=start_date_value,
            end_date=end_date_value,
            is_current=is_current,
            is_active=True,
        )
        session.add(term)
    else:
        term.start_date = start_date_value
        term.end_date = end_date_value
        term.is_current = is_current
        term.is_active = True

    await session.flush()
    return term


async def ensure_grading_scale(
    session,
    *,
    tenant_id: uuid.UUID,
    grade: str,
    min_score: Decimal,
    max_score: Decimal,
    remark: str,
) -> GradingScale:
    scale = await scalar_one_or_none(
        session,
        select(GradingScale).where(
            GradingScale.tenant_id == tenant_id,
            GradingScale.grade == grade,
        ),
    )
    if scale is None:
        scale = GradingScale(
            tenant_id=tenant_id,
            grade=grade,
            min_score=min_score,
            max_score=max_score,
            remark=remark,
            is_active=True,
        )
        session.add(scale)
    else:
        scale.min_score = min_score
        scale.max_score = max_score
        scale.remark = remark
        scale.is_active = True

    await session.flush()
    return scale


async def ensure_class_subject(
    session,
    *,
    tenant_id: uuid.UUID,
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    is_core: bool,
) -> ClassSubject:
    class_subject = await scalar_one_or_none(
        session,
        select(ClassSubject).where(
            ClassSubject.tenant_id == tenant_id,
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
        ),
    )
    if class_subject is None:
        class_subject = ClassSubject(
            tenant_id=tenant_id,
            class_id=class_id,
            subject_id=subject_id,
            is_core=is_core,
            is_active=True,
        )
        session.add(class_subject)
    else:
        class_subject.is_core = is_core
        class_subject.is_active = True

    await session.flush()
    return class_subject


async def ensure_teacher_assignment(
    session,
    *,
    tenant_id: uuid.UUID,
    class_subject_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> TeacherAssignment:
    assignment = await scalar_one_or_none(
        session,
        select(TeacherAssignment).where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.class_subject_id == class_subject_id,
            TeacherAssignment.is_active.is_(True),
        ),
    )
    if assignment is None:
        assignment = TeacherAssignment(
            tenant_id=tenant_id,
            class_subject_id=class_subject_id,
            teacher_id=teacher_id,
            is_active=True,
            effective_from=date(2026, 5, 4),
            effective_to=None,
        )
        session.add(assignment)
    else:
        assignment.teacher_id = teacher_id
        assignment.is_active = True
        assignment.effective_from = date(2026, 5, 4)
        assignment.effective_to = None

    await session.flush()
    return assignment


async def ensure_legacy_class_subject_teacher(
    session,
    *,
    tenant_id: uuid.UUID,
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    teacher_id: uuid.UUID,
    is_core: bool,
) -> ClassSubjectTeacher:
    legacy = await scalar_one_or_none(
        session,
        select(ClassSubjectTeacher).where(
            ClassSubjectTeacher.tenant_id == tenant_id,
            ClassSubjectTeacher.class_id == class_id,
            ClassSubjectTeacher.subject_id == subject_id,
        ),
    )
    if legacy is None:
        legacy = ClassSubjectTeacher(
            tenant_id=tenant_id,
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            is_core=is_core,
            sort_order=0,
            is_active=True,
        )
        session.add(legacy)
    else:
        legacy.teacher_id = teacher_id
        legacy.is_core = is_core
        legacy.is_active = True

    await session.flush()
    return legacy


async def ensure_result(
    session,
    *,
    tenant_id: uuid.UUID,
    student: Student,
    class_subject: ClassSubject,
    legacy_assignment: ClassSubjectTeacher,
    teacher_assignment: TeacherAssignment,
    academic_session: AcademicSession,
    academic_term: AcademicTerm,
    recorded_by_actor_id: uuid.UUID,
    test_score: Decimal,
    assessment_score: Decimal,
    exam_score: Decimal,
) -> StudentSubjectResult:
    total_score = test_score + assessment_score + exam_score
    grade, remark = resolve_grade(total_score)
    result = await scalar_one_or_none(
        session,
        select(StudentSubjectResult).where(
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.student_id == student.id,
            StudentSubjectResult.class_subject_teacher_id == legacy_assignment.id,
            StudentSubjectResult.academic_session_id == academic_session.id,
            StudentSubjectResult.academic_term_id == academic_term.id,
        ),
    )
    if result is None:
        result = StudentSubjectResult(
            tenant_id=tenant_id,
            student_id=student.id,
            class_id=class_subject.class_id,
            subject_id=class_subject.subject_id,
            teacher_id=teacher_assignment.teacher_id,
            class_subject_teacher_id=legacy_assignment.id,
            teacher_assignment_id=teacher_assignment.id,
            academic_session_id=academic_session.id,
            academic_term_id=academic_term.id,
            recorded_by_actor_type=ActorType.TENANT_ADMIN.value,
            recorded_by_actor_id=recorded_by_actor_id,
            test_score=test_score,
            assessment_score=assessment_score,
            exam_score=exam_score,
            total_score=total_score,
            grade=grade,
            remark=remark,
            status=AcademicResultStatus.SUBMITTED,
        )
        session.add(result)
    else:
        result.teacher_id = teacher_assignment.teacher_id
        result.teacher_assignment_id = teacher_assignment.id
        result.test_score = test_score
        result.assessment_score = assessment_score
        result.exam_score = exam_score
        result.total_score = total_score
        result.grade = grade
        result.remark = remark
        result.status = AcademicResultStatus.SUBMITTED
        result.recorded_by_actor_type = ActorType.TENANT_ADMIN.value
        result.recorded_by_actor_id = recorded_by_actor_id

    await session.flush()
    return result


def resolve_grade(total_score: Decimal) -> tuple[str, str]:
    if total_score >= Decimal("70"):
        return "A", "Excellent"
    if total_score >= Decimal("60"):
        return "B", "Very Good"
    if total_score >= Decimal("50"):
        return "C", "Good"
    if total_score >= Decimal("45"):
        return "D", "Fair"
    if total_score >= Decimal("40"):
        return "E", "Pass"
    return "F", "Fail"


def build_seed_data(admission_prefix: str) -> tuple[
    list[TeacherSeed],
    list[ParentSeed],
    list[ClassSeed],
    list[StudentSeed],
]:
    teachers = [
        TeacherSeed("testteacher1@gmail.com", "Ada", "Okafor", "TCH-001", "B.Ed", "Mathematics"),
        TeacherSeed("testteacher2@gmail.com", "Kunle", "Adewale", "TCH-002", "B.A", "English Language"),
        TeacherSeed("testteacher3@gmail.com", "Mariam", "Bello", "TCH-003", "B.Sc", "Basic Science"),
        TeacherSeed("testteacher4@gmail.com", "Chinedu", "Ike", "TCH-004", "B.Tech", "Computer Studies"),
        TeacherSeed("testteacher5@gmail.com", "Aisha", "Yusuf", "TCH-005", "B.Ed", "Social Studies"),
    ]
    parents = [
        ParentSeed("testparent1@gmail.com", "Michael", "Okafor", "08030000001", "Trader"),
        ParentSeed("testparent2@gmail.com", "Sarah", "Adewale", "08030000002", "Nurse"),
        ParentSeed("testparent3@gmail.com", "Ibrahim", "Bello", "08030000003", "Engineer"),
        ParentSeed("testparent4@gmail.com", "Ngozi", "Ike", "08030000004", "Civil Servant"),
    ]
    classes = [
        ClassSeed("jss1a", "JSS 1", "Junior Secondary 1", "A", "testteacher1@gmail.com"),
        ClassSeed("jss1b", "JSS 1", "Junior Secondary 1", "B", "testteacher2@gmail.com"),
        ClassSeed("jss2a", "JSS 2", "Junior Secondary 2", "A", "testteacher3@gmail.com"),
    ]
    students = [
        StudentSeed(f"{admission_prefix}2600001", "John", "Okafor", "jss1a", Gender.MALE, date(2014, 2, 14), "testparent1@gmail.com", ParentRelationship.FATHER),
        StudentSeed(f"{admission_prefix}2600002", "Mary", "Okafor", "jss1a", Gender.FEMALE, date(2014, 5, 9), "testparent1@gmail.com", ParentRelationship.MOTHER),
        StudentSeed(f"{admission_prefix}2600003", "Daniel", "Adewale", "jss1b", Gender.MALE, date(2013, 10, 21), "testparent2@gmail.com", ParentRelationship.MOTHER),
        StudentSeed(f"{admission_prefix}2600004", "Esther", "Adewale", "jss1b", Gender.FEMALE, date(2014, 1, 17), "testparent2@gmail.com", ParentRelationship.MOTHER),
        StudentSeed(f"{admission_prefix}2600005", "Samuel", "Bello", "jss2a", Gender.MALE, date(2012, 7, 3), "testparent3@gmail.com", ParentRelationship.FATHER),
        StudentSeed(f"{admission_prefix}2600006", "Ruth", "Bello", "jss2a", Gender.FEMALE, date(2012, 11, 11), "testparent3@gmail.com", ParentRelationship.MOTHER),
        StudentSeed(f"{admission_prefix}2600007", "Grace", "Ike", "jss1a", Gender.FEMALE, date(2014, 8, 29), "testparent4@gmail.com", ParentRelationship.GUARDIAN),
        StudentSeed(f"{admission_prefix}2600008", "David", "Ike", "jss2a", Gender.MALE, date(2013, 4, 8), "testparent4@gmail.com", ParentRelationship.GUARDIAN),
    ]
    return teachers, parents, classes, students


async def seed(tenant_id_arg: str | None) -> None:
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    async with AsyncSessionLocal() as session:
        tenant = await resolve_target_tenant(session, tenant_id_arg)
        await ensure_tenant_ready(session, tenant)

        tenant_admin = await scalar_one_or_none(
            session,
            select(TenantAdmin).where(TenantAdmin.tenant_id == tenant.id).order_by(TenantAdmin.created_at.asc()),
        )
        if tenant_admin is None:
            raise ValueError("Tenant has no tenant_admin record, so result/audit records cannot be attributed safely.")

        teachers_seed, parents_seed, classes_seed, students_seed = build_seed_data(
            tenant.admission_number_prefix or "DBS"
        )

        teachers_by_email: dict[str, Teacher] = {}
        for payload in teachers_seed:
            teacher = await ensure_teacher(session, tenant_id=tenant.id, payload=payload)
            teachers_by_email[payload.email] = teacher

        parents_by_email: dict[str, Parent] = {}
        for payload in parents_seed:
            parent = await ensure_parent(session, tenant_id=tenant.id, payload=payload)
            parents_by_email[payload.email] = parent

        classrooms_by_key: dict[str, ClassRoom] = {}
        for payload in classes_seed:
            teacher = teachers_by_email[payload.homeroom_teacher_email]
            classroom = await ensure_classroom(
                session,
                tenant_id=tenant.id,
                payload=payload,
                teacher_id=teacher.id,
            )
            classrooms_by_key[payload.key] = classroom

        subjects_by_code: dict[str, Subject] = {}
        subject_seed = [
            ("MTH", "Mathematics", "Core mathematics subject"),
            ("ENG", "English Language", "Reading, grammar, and writing"),
            ("BST", "Basic Science", "Integrated junior science"),
            ("SOS", "Social Studies", "Society and civic awareness"),
            ("CIV", "Civic Education", "Citizenship and values"),
            ("CMP", "Computer Studies", "Digital literacy and computing"),
        ]
        for code, name, description in subject_seed:
            subject = await ensure_subject(
                session,
                tenant_id=tenant.id,
                name=name,
                code=code,
                description=description,
            )
            subjects_by_code[code] = subject

        teacher_subject_map = {
            "testteacher1@gmail.com": ["MTH"],
            "testteacher2@gmail.com": ["ENG"],
            "testteacher3@gmail.com": ["BST"],
            "testteacher4@gmail.com": ["CMP", "CIV"],
            "testteacher5@gmail.com": ["SOS"],
        }
        for email, codes in teacher_subject_map.items():
            teacher = teachers_by_email[email]
            for code in codes:
                await ensure_teacher_subject(
                    session,
                    tenant_id=tenant.id,
                    teacher_id=teacher.id,
                    subject_id=subjects_by_code[code].id,
                )

        academic_session = await ensure_academic_session(session, tenant_id=tenant.id)
        await ensure_academic_term(
            session,
            tenant_id=tenant.id,
            academic_session_id=academic_session.id,
            name=AcademicTermName.FIRST_TERM,
            start_date_value=date(2025, 9, 8),
            end_date_value=date(2025, 12, 19),
            is_current=False,
        )
        await ensure_academic_term(
            session,
            tenant_id=tenant.id,
            academic_session_id=academic_session.id,
            name=AcademicTermName.SECOND_TERM,
            start_date_value=date(2026, 1, 12),
            end_date_value=date(2026, 4, 10),
            is_current=False,
        )
        current_term = await ensure_academic_term(
            session,
            tenant_id=tenant.id,
            academic_session_id=academic_session.id,
            name=AcademicTermName.THIRD_TERM,
            start_date_value=date(2026, 5, 4),
            end_date_value=date(2026, 7, 31),
            is_current=True,
        )

        grading_seed = [
            ("A", Decimal("70"), Decimal("100"), "Excellent"),
            ("B", Decimal("60"), Decimal("69.99"), "Very Good"),
            ("C", Decimal("50"), Decimal("59.99"), "Good"),
            ("D", Decimal("45"), Decimal("49.99"), "Fair"),
            ("E", Decimal("40"), Decimal("44.99"), "Pass"),
            ("F", Decimal("0"), Decimal("39.99"), "Fail"),
        ]
        for grade, min_score, max_score, remark in grading_seed:
            await ensure_grading_scale(
                session,
                tenant_id=tenant.id,
                grade=grade,
                min_score=min_score,
                max_score=max_score,
                remark=remark,
            )

        students_by_admission: dict[str, Student] = {}
        for payload in students_seed:
            classroom = classrooms_by_key[payload.class_key]
            student = await ensure_student(
                session,
                tenant_id=tenant.id,
                payload=payload,
                classroom=classroom,
            )
            students_by_admission[payload.admission_number] = student
            parent = parents_by_email[payload.parent_email]
            await ensure_parent_link(
                session,
                tenant_id=tenant.id,
                student_id=student.id,
                parent_id=parent.id,
                relationship_type=payload.relationship_type,
                is_primary_contact=True,
            )

        class_subject_teacher_map = {
            "jss1a": [("MTH", "testteacher1@gmail.com"), ("ENG", "testteacher2@gmail.com"), ("BST", "testteacher3@gmail.com"), ("CMP", "testteacher4@gmail.com")],
            "jss1b": [("MTH", "testteacher1@gmail.com"), ("ENG", "testteacher2@gmail.com"), ("SOS", "testteacher5@gmail.com"), ("CIV", "testteacher4@gmail.com")],
            "jss2a": [("MTH", "testteacher1@gmail.com"), ("ENG", "testteacher2@gmail.com"), ("BST", "testteacher3@gmail.com"), ("SOS", "testteacher5@gmail.com")],
        }

        assignment_bundle_by_class_subject: dict[tuple[uuid.UUID, uuid.UUID], tuple[ClassSubject, ClassSubjectTeacher, TeacherAssignment]] = {}
        for class_key, pairs in class_subject_teacher_map.items():
            classroom = classrooms_by_key[class_key]
            for subject_code, teacher_email in pairs:
                subject = subjects_by_code[subject_code]
                teacher = teachers_by_email[teacher_email]
                class_subject = await ensure_class_subject(
                    session,
                    tenant_id=tenant.id,
                    class_id=classroom.id,
                    subject_id=subject.id,
                    is_core=True,
                )
                legacy = await ensure_legacy_class_subject_teacher(
                    session,
                    tenant_id=tenant.id,
                    class_id=classroom.id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                    is_core=True,
                )
                assignment = await ensure_teacher_assignment(
                    session,
                    tenant_id=tenant.id,
                    class_subject_id=class_subject.id,
                    teacher_id=teacher.id,
                )
                assignment_bundle_by_class_subject[(classroom.id, subject.id)] = (class_subject, legacy, assignment)

        ordered_subject_codes = ["MTH", "ENG", "BST", "SOS", "CIV", "CMP"]
        for index, payload in enumerate(students_seed, start=1):
            student = students_by_admission[payload.admission_number]
            classroom = classrooms_by_key[payload.class_key]
            offered_pairs = class_subject_teacher_map[payload.class_key]
            for subject_position, (subject_code, _teacher_email) in enumerate(offered_pairs, start=1):
                subject = subjects_by_code[subject_code]
                class_subject, legacy, assignment = assignment_bundle_by_class_subject[(classroom.id, subject.id)]
                subject_bias = ordered_subject_codes.index(subject_code) if subject_code in ordered_subject_codes else subject_position
                test_score = Decimal(str(12 + ((index + subject_bias) % 8)))
                assessment_score = Decimal(str(14 + ((index * 2 + subject_bias) % 8)))
                exam_score = Decimal(str(40 + ((index * 3 + subject_bias) % 21)))
                await ensure_result(
                    session,
                    tenant_id=tenant.id,
                    student=student,
                    class_subject=class_subject,
                    legacy_assignment=legacy,
                    teacher_assignment=assignment,
                    academic_session=academic_session,
                    academic_term=current_term,
                    recorded_by_actor_id=tenant_admin.id,
                    test_score=test_score,
                    assessment_score=assessment_score,
                    exam_score=exam_score,
                )

        await session.commit()

    print(f"Seeded tenant: {tenant.school_name} ({tenant.id})")
    print(f"Default password for teachers, parents, and students: {DEFAULT_PASSWORD}")
    print("Created or updated:")
    print("  - 5 teachers")
    print("  - 4 parents")
    print("  - 8 students")
    print("  - 3 classes")
    print("  - 6 subjects")
    print("  - 1 academic session with 3 terms")
    print("  - 6 grading scale rows")
    print("  - class subjects, teacher assignments, parent links, and submitted results")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the current tenant with dummy academic workflow data.")
    parser.add_argument(
        "--tenant-id",
        help="Explicit tenant ID to seed. Required when more than one tenant exists.",
    )
    return parser.parse_args()

async def main() -> None:
    args = parse_args()
    await seed(args.tenant_id)
    await verify_logins(args.tenant_id)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
