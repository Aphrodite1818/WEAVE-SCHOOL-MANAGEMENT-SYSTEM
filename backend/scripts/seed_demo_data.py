from __future__ import annotations

import argparse
import asyncio
import random
import sys
import uuid
from datetime import date
from pathlib import Path

from faker import Faker
from sqlalchemy import delete, select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.database import AsyncSessionLocal, engine
from app.config.security import hash_password
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.classes.models import ClassRoom
from app.modules.students.models import (
    AcademicStatus,
    Gender,
    Student,
    StudentAccountStatus,
    StudentProfileStatus,
)
from app.modules.subjects.models import Subject
from app.tenant_management.models import Tenant

DEFAULT_PASSWORD = "Test12345!"
SEED_TAG = "demo-seed"
DEFAULT_STUDENT_COUNT = 600
DEFAULT_SEED = 20260727

CLASS_NAMES = ["JSS 1", "JSS 2", "JSS 3", "SS 1", "SS 2", "SS 3"]
ARMS = ["A", "B", "C", "D"]
SUBJECTS = [
    ("MTH", "Mathematics"),
    ("ENG", "English Language"),
    ("BST", "Basic Science"),
    ("BTE", "Basic Technology"),
    ("CMP", "Computer Studies"),
    ("SOS", "Social Studies"),
    ("CIV", "Civic Education"),
    ("BUS", "Business Studies"),
    ("PHY", "Physics"),
    ("CHE", "Chemistry"),
    ("BIO", "Biology"),
    ("ECO", "Economics"),
    ("ACC", "Financial Accounting"),
    ("GOV", "Government"),
    ("LIT", "Literature in English"),
    ("CRS", "Christian Religious Studies"),
]

fake = Faker("en_NG")


def normalize_email(value: str) -> str:
    return value.strip().lower()


async def resolve_tenant(session, tenant_id: str | None) -> Tenant:
    if tenant_id:
        tenant = await session.get(Tenant, uuid.UUID(tenant_id))
        if tenant is None:
            raise ValueError(f"Tenant {tenant_id} was not found.")
        return tenant

    tenants = list((await session.execute(select(Tenant).order_by(Tenant.created_at.asc()))).scalars().all())
    if not tenants:
        raise ValueError("No tenant exists. Create a school first, then rerun the seeder.")
    if len(tenants) > 1:
        raise ValueError("Multiple tenants exist. Pass --tenant-id to select the school to seed.")
    return tenants[0]


async def purge_seed_data(session, tenant_id: uuid.UUID) -> None:
    student_ids = list((await session.execute(
        select(Student.id).where(
            Student.tenant_id == tenant_id,
            Student.admission_number.like("DEMO-%"),
        )
    )).scalars().all())

    if student_ids:
        await session.execute(delete(AuthIdentity).where(
            AuthIdentity.actor_type == ActorType.STUDENT,
            AuthIdentity.actor_id.in_(student_ids),
        ))
        await session.execute(delete(Student).where(Student.id.in_(student_ids)))

    await session.execute(delete(ClassRoom).where(
        ClassRoom.tenant_id == tenant_id,
        ClassRoom.name.in_(CLASS_NAMES),
    ))
    await session.execute(delete(Subject).where(
        Subject.tenant_id == tenant_id,
        Subject.code.in_([code for code, _ in SUBJECTS]),
    ))
    await session.commit()


async def ensure_subjects(session, tenant_id: uuid.UUID) -> list[Subject]:
    rows: list[Subject] = []
    for code, name in SUBJECTS:
        subject = (await session.execute(select(Subject).where(
            Subject.tenant_id == tenant_id,
            Subject.code == code,
        ))).scalar_one_or_none()
        if subject is None:
            subject = Subject(
                tenant_id=tenant_id,
                name=name,
                code=code,
                description=f"{name} subject",
                is_active=True,
            )
            session.add(subject)
            await session.flush()
        rows.append(subject)
    return rows


async def ensure_classes(session, tenant_id: uuid.UUID) -> list[ClassRoom]:
    rows: list[ClassRoom] = []
    previous_by_arm: dict[str, ClassRoom] = {}

    for class_name in CLASS_NAMES:
        for arm in ARMS:
            classroom = (await session.execute(select(ClassRoom).where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.name == class_name,
                ClassRoom.arm == arm,
            ))).scalar_one_or_none()

            if classroom is None:
                classroom = ClassRoom(
                    tenant_id=tenant_id,
                    name=class_name,
                    arm=arm,
                    is_active=True,
                    is_terminal=class_name == "SS 3",
                )
                session.add(classroom)
                await session.flush()

            previous = previous_by_arm.get(arm)
            if previous is not None:
                previous.next_class_id = classroom.id
            previous_by_arm[arm] = classroom
            rows.append(classroom)

    await session.flush()
    return rows


async def create_students(
    session,
    tenant: Tenant,
    classes: list[ClassRoom],
    count: int,
) -> None:
    admission_prefix = (tenant.admission_number_prefix or "DEMO").upper()

    for index in range(1, count + 1):
        admission_number = f"DEMO-{admission_prefix}-{index:05d}"
        exists = (await session.execute(select(Student.id).where(
            Student.tenant_id == tenant.id,
            Student.admission_number == admission_number,
        ))).scalar_one_or_none()
        if exists:
            continue

        classroom = classes[(index - 1) % len(classes)]
        gender = Gender.MALE if index % 2 == 0 else Gender.FEMALE
        first_name = fake.first_name_male() if gender == Gender.MALE else fake.first_name_female()
        last_name = fake.last_name()

        status_roll = random.random()
        status = AcademicStatus.ACTIVE
        is_active = True
        if status_roll < 0.015:
            status = AcademicStatus.SUSPENDED
        elif status_roll < 0.025:
            status = AcademicStatus.WITHDRAWN
            is_active = False

        student = Student(
            tenant_id=tenant.id,
            admission_number=admission_number,
            password_hash=hash_password(DEFAULT_PASSWORD),
            first_name=first_name,
            last_name=last_name,
            account_status=StudentAccountStatus.ACTIVE,
            is_verified=True,
            is_active=is_active,
            password_reset_required=False,
            date_of_birth=date(2010 + (index % 7), 1 + (index % 12), 1 + (index % 27)),
            gender=gender,
            state_of_origin=fake.state(),
            class_id=classroom.id,
            arm=classroom.arm,
            status=status,
            profile_status=StudentProfileStatus.COMPLETE,
        )
        session.add(student)
        await session.flush()

        session.add(AuthIdentity(
            tenant_id=tenant.id,
            identifier=admission_number,
            identifier_type=IdentifierType.ADMISSION_NUMBER,
            actor_type=ActorType.STUDENT,
            actor_id=student.id,
            is_active=is_active,
        ))

        if index % 100 == 0:
            await session.commit()
            print(f"Created {index}/{count} students...")

    await session.commit()


async def seed(tenant_id: str | None, students: int, reset: bool, seed_value: int) -> None:
    Faker.seed(seed_value)
    random.seed(seed_value)

    async with AsyncSessionLocal() as session:
        tenant = await resolve_tenant(session, tenant_id)
        print(f"Seeding tenant: {tenant.school_name} ({tenant.id})")

        if reset:
            await purge_seed_data(session, tenant.id)

        subjects = await ensure_subjects(session, tenant.id)
        classes = await ensure_classes(session, tenant.id)
        await session.commit()

        await create_students(session, tenant, classes, students)

        print("\nDemo seed complete")
        print(f"Subjects: {len(subjects)}")
        print(f"Classes: {len(classes)}")
        print(f"Students requested: {students}")
        print(f"Student password: {DEFAULT_PASSWORD}")

    await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed current-schema Weave demo data.")
    parser.add_argument("--tenant-id", help="Tenant UUID. Required when the database has multiple tenants.")
    parser.add_argument("--students", type=int, default=DEFAULT_STUDENT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--reset", action="store_true", help="Delete rows created by this seeder before regenerating them.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed(args.tenant_id, args.students, args.reset, args.seed))
