from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.database import AsyncSessionLocal, engine
from app.config.security import hash_password
from app.core.utils.normalization import (
    normalize_admission_number,
    normalize_class_arm,
    normalize_class_name,
    normalize_email,
    normalize_grade,
    normalize_staff_id,
    normalize_subject_code,
    normalize_subject_name,
    normalized_class_arm_key,
    normalized_class_name_key,
)
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.student_academics.models import GradingScale
from app.modules.students.models import (
    AcademicStatus,
    Gender,
    Student,
    StudentAccountStatus,
    StudentProfileStatus,
)
from app.modules.subjects.models import Subject
from app.modules.teachers.models import Teacher, TeacherAccountStatus, TeacherStatus
from app.tenant_management.models import Tenant


DEFAULT_PASSWORD = "Test12345!"


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
        raise ValueError("No tenants exist in the database. Create a tenant first or pass --tenant-id.")
    if len(tenants) > 1:
        raise ValueError("Multiple tenants found. Re-run with --tenant-id to avoid seeding the wrong school.")
    return tenants[0]


async def ensure_auth_identity(
    session,
    *,
    tenant_id: uuid.UUID,
    identifier: str,
    identifier_type: IdentifierType,
    actor_type: ActorType,
    actor_id: uuid.UUID,
) -> AuthIdentity:
    if identifier_type == IdentifierType.EMAIL:
        normalized_identifier = normalize_email(identifier)
    elif identifier_type == IdentifierType.ADMISSION_NUMBER:
        normalized_identifier = normalize_admission_number(identifier)
    else:
        normalized_identifier = identifier.strip()

    if normalized_identifier is None:
        raise ValueError("identifier cannot be empty")

    result = await session.execute(
        select(AuthIdentity).where(
            AuthIdentity.identifier == normalized_identifier,
            AuthIdentity.identifier_type == identifier_type,
        )
    )
    identity = result.scalar_one_or_none()

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
    identity.actor_type = actor_type
    identity.actor_id = actor_id
    identity.is_active = True
    await session.flush()
    return identity


async def ensure_teacher(
    session,
    *,
    tenant_id: uuid.UUID,
    email: str,
    staff_id: str,
    first_name: str,
    last_name: str,
    specialization: str,
) -> Teacher:
    normalized_email = normalize_email(email)
    normalized_staff_id = normalize_staff_id(staff_id)
    if normalized_email is None or normalized_staff_id is None:
        raise ValueError("teacher email and staff_id are required")

    result = await session.execute(
        select(Teacher).where(
            Teacher.tenant_id == tenant_id,
            Teacher.staff_id == normalized_staff_id,
        )
    )
    teacher = result.scalar_one_or_none()

    if teacher is None:
        teacher = Teacher(
            tenant_id=tenant_id,
            email=normalized_email,
            password_hash=hash_password(DEFAULT_PASSWORD),
            first_name=first_name,
            last_name=last_name,
            staff_id=normalized_staff_id,
            qualification="B.Ed",
            specialization=specialization,
            account_status=TeacherAccountStatus.ACTIVE,
            status=TeacherStatus.ACTIVE,
            is_verified=True,
            is_active=True,
        )
        session.add(teacher)
        await session.flush()
    else:
        teacher.email = normalized_email
        teacher.first_name = first_name
        teacher.last_name = last_name
        teacher.specialization = specialization
        teacher.account_status = TeacherAccountStatus.ACTIVE
        teacher.status = TeacherStatus.ACTIVE
        teacher.is_verified = True
        teacher.is_active = True
        await session.flush()

    await ensure_auth_identity(
        session,
        tenant_id=tenant_id,
        identifier=normalized_email,
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.TEACHER,
        actor_id=teacher.id,
    )
    return teacher


async def ensure_classroom(
    session,
    *,
    tenant_id: uuid.UUID,
    name: str,
    arm: str | None,
    teacher_id: uuid.UUID | None = None,
) -> ClassRoom:
    display_name = normalize_class_name(name)
    display_arm = normalize_class_arm(arm)
    normalized_name = normalized_class_name_key(name)
    normalized_arm = normalized_class_arm_key(arm)

    if display_name is None or normalized_name is None:
        raise ValueError("class name cannot be empty")

    result = await session.execute(
        select(ClassRoom).where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.normalized_name == normalized_name,
            ClassRoom.normalized_arm == normalized_arm,
        )
    )
    classroom = result.scalar_one_or_none()

    if classroom is None:
        classroom = ClassRoom(
            tenant_id=tenant_id,
            name=display_name,
            normalized_name=normalized_name,
            arm=display_arm,
            normalized_arm=normalized_arm,
            teacher_id=teacher_id,
            is_active=True,
        )
        session.add(classroom)
        await session.flush()
        return classroom

    classroom.name = display_name
    classroom.normalized_name = normalized_name
    classroom.arm = display_arm
    classroom.normalized_arm = normalized_arm
    classroom.teacher_id = teacher_id
    classroom.is_active = True
    await session.flush()
    return classroom


async def ensure_subject(session, *, tenant_id: uuid.UUID, name: str, code: str) -> Subject:
    normalized_name = normalize_subject_name(name)
    normalized_code = normalize_subject_code(code)
    if normalized_name is None:
        raise ValueError("subject name cannot be empty")

    result = await session.execute(
        select(Subject).where(
            Subject.tenant_id == tenant_id,
            Subject.normalized_name == normalized_name,
        )
    )
    subject = result.scalar_one_or_none()

    if subject is None:
        subject = Subject(
            tenant_id=tenant_id,
            name=" ".join(name.strip().split()).title(),
            normalized_name=normalized_name,
            code=normalized_code,
            normalized_code=normalized_code,
            description=f"Seeded {name} subject",
            is_active=True,
        )
        session.add(subject)
        await session.flush()
        return subject

    subject.name = " ".join(name.strip().split()).title()
    subject.code = normalized_code
    subject.normalized_code = normalized_code
    subject.is_active = True
    await session.flush()
    return subject


async def ensure_grading_scale(
    session,
    *,
    tenant_id: uuid.UUID,
    grade: str,
    min_score: Decimal,
    max_score: Decimal,
    remark: str,
) -> GradingScale:
    normalized_grade = normalize_grade(grade)
    if normalized_grade is None:
        raise ValueError("grade cannot be empty")

    result = await session.execute(
        select(GradingScale).where(
            GradingScale.tenant_id == tenant_id,
            GradingScale.grade == normalized_grade,
        )
    )
    scale = result.scalar_one_or_none()

    if scale is None:
        scale = GradingScale(
            tenant_id=tenant_id,
            grade=normalized_grade,
            min_score=min_score,
            max_score=max_score,
            remark=remark,
            is_active=True,
        )
        session.add(scale)
        await session.flush()
        return scale

    scale.min_score = min_score
    scale.max_score = max_score
    scale.remark = remark
    scale.is_active = True
    await session.flush()
    return scale


async def ensure_parent(
    session,
    *,
    tenant_id: uuid.UUID,
    email: str,
    first_name: str,
    last_name: str,
) -> Parent:
    normalized_email = normalize_email(email)
    if normalized_email is None:
        raise ValueError("parent email cannot be empty")

    result = await session.execute(
        select(Parent).where(Parent.email == normalized_email)
    )
    parent = result.scalar_one_or_none()

    if parent is None:
        parent = Parent(
            tenant_id=tenant_id,
            email=normalized_email,
            password_hash=hash_password(DEFAULT_PASSWORD),
            first_name=first_name,
            last_name=last_name,
            phone_number="+2348012345678",
            occupation="Engineer",
            address="12 Normalized Seed Street",
            emergency_phone="+2348098765432",
            account_status=ParentAccountStatus.ACTIVE,
            is_verified=True,
            is_active=True,
        )
        session.add(parent)
        await session.flush()
    else:
        parent.tenant_id = tenant_id
        parent.first_name = first_name
        parent.last_name = last_name
        parent.account_status = ParentAccountStatus.ACTIVE
        parent.is_verified = True
        parent.is_active = True
        await session.flush()

    await ensure_auth_identity(
        session,
        tenant_id=tenant_id,
        identifier=normalized_email,
        identifier_type=IdentifierType.EMAIL,
        actor_type=ActorType.PARENT,
        actor_id=parent.id,
    )
    return parent


async def ensure_student(
    session,
    *,
    tenant_id: uuid.UUID,
    admission_number: str,
    first_name: str,
    last_name: str,
    classroom: ClassRoom,
    gender: Gender,
) -> Student:
    normalized_admission_number = normalize_admission_number(admission_number)
    if normalized_admission_number is None:
        raise ValueError("admission number cannot be empty")

    result = await session.execute(
        select(Student).where(
            Student.tenant_id == tenant_id,
            Student.admission_number == normalized_admission_number,
        )
    )
    student = result.scalar_one_or_none()

    if student is None:
        student = Student(
            tenant_id=tenant_id,
            admission_number=normalized_admission_number,
            password_hash=hash_password(DEFAULT_PASSWORD),
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date(2012, 9, 20),
            gender=gender,
            admission_date=date.today(),
            class_id=classroom.id,
            arm=classroom.arm,
            status=AcademicStatus.ACTIVE,
            account_status=StudentAccountStatus.ACTIVE,
            is_verified=True,
            is_active=True,
            password_reset_required=True,
            profile_status=StudentProfileStatus.COMPLETE,
            state_of_origin="Lagos",
        )
        session.add(student)
        await session.flush()
    else:
        student.first_name = first_name
        student.last_name = last_name
        student.gender = gender
        student.class_id = classroom.id
        student.arm = classroom.arm
        student.is_active = True
        student.status = AcademicStatus.ACTIVE
        student.profile_status = StudentProfileStatus.COMPLETE
        await session.flush()

    await ensure_auth_identity(
        session,
        tenant_id=tenant_id,
        identifier=normalized_admission_number,
        identifier_type=IdentifierType.ADMISSION_NUMBER,
        actor_type=ActorType.STUDENT,
        actor_id=student.id,
    )
    return student


async def seed(tenant_id_arg: str | None) -> None:
    async with AsyncSessionLocal() as session:
        tenant = await resolve_target_tenant(session, tenant_id_arg)
        tenant.admission_number_prefix = (tenant.admission_number_prefix or "DBS").upper()

        teacher = await ensure_teacher(
            session,
            tenant_id=tenant.id,
            email="normalized.teacher@example.com",
            staff_id="tch-001",
            first_name="Nora",
            last_name="Teacher",
            specialization="Mathematics",
        )

        class_no_arm = await ensure_classroom(
            session,
            tenant_id=tenant.id,
            name="jss 1",
            arm=None,
            teacher_id=teacher.id,
        )
        class_a = await ensure_classroom(
            session,
            tenant_id=tenant.id,
            name="JSS-1",
            arm="a",
            teacher_id=teacher.id,
        )
        class_b = await ensure_classroom(
            session,
            tenant_id=tenant.id,
            name="Jss1",
            arm=" B ",
            teacher_id=teacher.id,
        )

        await ensure_subject(session, tenant_id=tenant.id, name="mathematics", code="math")
        await ensure_subject(session, tenant_id=tenant.id, name="english language", code="eng")
        await ensure_subject(session, tenant_id=tenant.id, name="basic science", code="bsci")

        await ensure_grading_scale(
            session,
            tenant_id=tenant.id,
            grade="a",
            min_score=Decimal("70"),
            max_score=Decimal("100"),
            remark="Excellent",
        )
        await ensure_grading_scale(
            session,
            tenant_id=tenant.id,
            grade="b",
            min_score=Decimal("60"),
            max_score=Decimal("69.99"),
            remark="Very Good",
        )

        await ensure_parent(
            session,
            tenant_id=tenant.id,
            email="normalized.parent@example.com",
            first_name="Perry",
            last_name="Parent",
        )

        prefix = tenant.admission_number_prefix or "WVS"
        await ensure_student(
            session,
            tenant_id=tenant.id,
            admission_number=f"{prefix}260001",
            first_name="Bola",
            last_name="Ahmed",
            classroom=class_no_arm,
            gender=Gender.MALE,
        )
        await ensure_student(
            session,
            tenant_id=tenant.id,
            admission_number=f"{prefix}260002",
            first_name="Ada",
            last_name="Okafor",
            classroom=class_a,
            gender=Gender.FEMALE,
        )
        await ensure_student(
            session,
            tenant_id=tenant.id,
            admission_number=f"{prefix}260003",
            first_name="Timi",
            last_name="Lawal",
            classroom=class_b,
            gender=Gender.MALE,
        )

        await session.commit()
        print("Seeded normalized fake data")
        print(f"tenant_id={tenant.id}")
        print("classes=JSS1, JSS1 A, JSS1 B")
        print("teacher=normalized.teacher@example.com / Test12345!")
        print(f"students={prefix}260001, {prefix}260002, {prefix}260003 / Test12345!")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fake data that obeys normalized backend rules.")
    parser.add_argument("--tenant-id", default=None, help="Tenant UUID. Required when more than one tenant exists.")
    args = parser.parse_args()

    try:
        await seed(args.tenant_id)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
