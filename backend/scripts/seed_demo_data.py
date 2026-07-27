from __future__ import annotations

import argparse
import asyncio
import random
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from faker import Faker
from sqlalchemy import delete, select, update

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.database import AsyncSessionLocal, engine
from app.config.security import hash_password
import app.models  # noqa: F401
from sqlalchemy.orm import configure_mappers

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
from app.tenant_management.models import (
    SubscriptionPlan,
    Tenant,
    TenantStatus,
    TenantVerificationStatus,
)

DEFAULT_PASSWORD = "Test12345!"
DEFAULT_SEED = 20260727
SEED_SLUG_PREFIX = "demo-"

fake = Faker("en_NG")


@dataclass(frozen=True)
class SchoolProfile:
    school_name: str
    slug: str
    prefix: str
    email_alias: str
    phone: str
    address: str
    city: str
    state: str
    status: TenantStatus
    plan: SubscriptionPlan
    student_count: int
    class_names: tuple[str, ...]
    arms: tuple[str, ...]
    subject_codes: tuple[str, ...]
    max_students: int
    max_teachers: int
    branches: tuple[str, ...] | None = None


SUBJECT_CATALOG: dict[str, tuple[str, str]] = {
    "MTH": ("Mathematics", "Numeracy, algebra, geometry and problem solving"),
    "ENG": ("English Language", "Reading, grammar, comprehension and writing"),
    "BST": ("Basic Science", "Integrated junior science"),
    "BTE": ("Basic Technology", "Introductory technology and design"),
    "CMP": ("Computer Studies", "Digital literacy and computing"),
    "SOS": ("Social Studies", "Society, culture and civic awareness"),
    "CIV": ("Civic Education", "Citizenship, rights and responsibilities"),
    "BUS": ("Business Studies", "Introductory business and entrepreneurship"),
    "PHY": ("Physics", "Mechanics, energy, waves and electricity"),
    "CHE": ("Chemistry", "Matter, reactions and laboratory science"),
    "BIO": ("Biology", "Living systems and ecology"),
    "ECO": ("Economics", "Markets, production and economic systems"),
    "ACC": ("Financial Accounting", "Bookkeeping and financial records"),
    "GOV": ("Government", "Political institutions and governance"),
    "LIT": ("Literature in English", "Drama, prose and poetry"),
    "CRS": ("Christian Religious Studies", "Christian faith and moral instruction"),
}


SCHOOL_PROFILES: tuple[SchoolProfile, ...] = (
    SchoolProfile(
        school_name="Cedar Grove College",
        slug="demo-cedar-grove",
        prefix="CGC",
        email_alias="cedargrove",
        phone="+2348031000001",
        address="14 Admiralty Way",
        city="Lekki",
        state="Lagos",
        status=TenantStatus.ACTIVE,
        plan=SubscriptionPlan.PROFESSIONAL,
        student_count=500,
        class_names=("JSS 1", "JSS 2", "JSS 3", "SS 1", "SS 2", "SS 3"),
        arms=("A", "B"),
        subject_codes=("MTH", "ENG", "BST", "BTE", "CMP", "SOS", "CIV", "PHY", "CHE", "BIO"),
        max_students=600,
        max_teachers=45,
    ),
    SchoolProfile(
        school_name="Northbridge Academy",
        slug="demo-northbridge-academy",
        prefix="NBA",
        email_alias="northbridge",
        phone="+2348031000002",
        address="8 Independence Avenue",
        city="Abuja",
        state="FCT",
        status=TenantStatus.TRIAL,
        plan=SubscriptionPlan.FREE_TRIAL,
        student_count=500,
        class_names=("JSS 1", "JSS 2", "JSS 3"),
        arms=("Gold",),
        subject_codes=("MTH", "ENG", "BST", "CMP", "SOS", "CIV", "BUS"),
        max_students=600,
        max_teachers=20,
    ),
    SchoolProfile(
        school_name="Bright Future Secondary School",
        slug="demo-bright-future",
        prefix="BFS",
        email_alias="brightfuture",
        phone="+2348031000003",
        address="22 Ring Road",
        city="Ibadan",
        state="Oyo",
        status=TenantStatus.ACTIVE,
        plan=SubscriptionPlan.PLUS,
        student_count=500,
        class_names=("JSS 1", "JSS 2", "JSS 3", "SS 1", "SS 2", "SS 3"),
        arms=("A", "B", "C"),
        subject_codes=("MTH", "ENG", "BST", "BTE", "CMP", "SOS", "CIV", "BUS", "BIO", "ECO", "GOV"),
        max_students=600,
        max_teachers=55,
    ),
    SchoolProfile(
        school_name="Royal Crest International School",
        slug="demo-royal-crest",
        prefix="RCI",
        email_alias="royalcrest",
        phone="+2348031000004",
        address="3 GRA Crescent",
        city="Port Harcourt",
        state="Rivers",
        status=TenantStatus.ACTIVE,
        plan=SubscriptionPlan.ENTERPRISE,
        student_count=500,
        class_names=("JSS 1", "JSS 2", "JSS 3", "SS 1", "SS 2", "SS 3"),
        arms=("A", "B", "C", "D"),
        subject_codes=tuple(SUBJECT_CATALOG.keys()),
        max_students=1500,
        max_teachers=120,
        branches=("Main Campus", "Annex Campus"),
    ),
    SchoolProfile(
        school_name="Unity Community College",
        slug="demo-unity-community",
        prefix="UCC",
        email_alias="unitycommunity",
        phone="+2348031000005",
        address="17 Emir Road",
        city="Kano",
        state="Kano",
        status=TenantStatus.SUSPENDED,
        plan=SubscriptionPlan.PLUS,
        student_count=500,
        class_names=("JSS 1", "JSS 2", "JSS 3", "SS 1"),
        arms=("A",),
        subject_codes=("MTH", "ENG", "BST", "CMP", "SOS", "CIV"),
        max_students=600,
        max_teachers=30,
    ),
)


def school_email(profile: SchoolProfile) -> str:
    return f"taiwoayimora623+{profile.email_alias}@gmail.com"


def admission_number(profile: SchoolProfile, index: int) -> str:
    return f"{profile.prefix}/26/{index:04d}"


def student_status(index: int, rng: random.Random) -> tuple[AcademicStatus, bool]:
    roll = rng.random()
    if roll < 0.02:
        return AcademicStatus.WITHDRAWN, False
    if roll < 0.03:
        return AcademicStatus.EXPELLED, False
    if roll < 0.06:
        return AcademicStatus.SUSPENDED, True
    if index % 97 == 0:
        return AcademicStatus.GRADUATED, False
    return AcademicStatus.ACTIVE, True


async def purge_demo_data(session) -> None:
    tenants = list(
        (
            await session.execute(
                select(Tenant).where(Tenant.slug.in_([profile.slug for profile in SCHOOL_PROFILES]))
            )
        )
        .scalars()
        .all()
    )
    if not tenants:
        return

    tenant_ids = [tenant.id for tenant in tenants]
    student_ids = list(
        (
            await session.execute(select(Student.id).where(Student.tenant_id.in_(tenant_ids)))
        )
        .scalars()
        .all()
    )

    if student_ids:
        await session.execute(
            delete(AuthIdentity).where(
                AuthIdentity.actor_type == ActorType.STUDENT,
                AuthIdentity.actor_id.in_(student_ids),
            )
        )
        await session.execute(delete(Student).where(Student.id.in_(student_ids)))

    await session.execute(
        update(ClassRoom)
        .where(ClassRoom.tenant_id.in_(tenant_ids))
        .values(next_class_id=None, teacher_membership_id=None)
    )
    await session.execute(delete(ClassRoom).where(ClassRoom.tenant_id.in_(tenant_ids)))
    await session.execute(delete(Subject).where(Subject.tenant_id.in_(tenant_ids)))
    await session.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))
    await session.commit()
    print(f"Removed {len(tenant_ids)} previously generated demo schools.")


async def ensure_tenant(session, profile: SchoolProfile) -> Tenant:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.slug == profile.slug))
    ).scalar_one_or_none()

    trial_ends_at = datetime.now(timezone.utc) + timedelta(days=30)
    if tenant is None:
        tenant = Tenant(
            school_name=profile.school_name,
            slug=profile.slug,
            admission_number_prefix=profile.prefix,
            email=school_email(profile),
            phone=profile.phone,
            address=profile.address,
            city=profile.city,
            state=profile.state,
            country="Nigeria",
            status=profile.status,
            plan=profile.plan,
            trial_ends_at=trial_ends_at if profile.status == TenantStatus.TRIAL else None,
            max_students=profile.max_students,
            max_teachers=profile.max_teachers,
            feature_flags={
                "demo_seed": True,
                "whatsapp_bot": profile.plan in {SubscriptionPlan.PROFESSIONAL, SubscriptionPlan.ENTERPRISE},
            },
            timezone="Africa/Lagos",
            language="en",
            onboarding_completed=True,
            branches=list(profile.branches) if profile.branches else None,
            verification_status=TenantVerificationStatus.ACTIVE,
        )
        session.add(tenant)
        await session.flush()
    return tenant


async def ensure_subjects(session, tenant: Tenant, profile: SchoolProfile) -> list[Subject]:
    subjects: list[Subject] = []
    for code in profile.subject_codes:
        name, description = SUBJECT_CATALOG[code]
        subject = (
            await session.execute(
                select(Subject).where(
                    Subject.tenant_id == tenant.id,
                    Subject.code == code,
                )
            )
        ).scalar_one_or_none()
        if subject is None:
            from app.modules.subjects.service import SubjectService
            subject = Subject(
                tenant_id=tenant.id,
                name=name,
                normalized_name=SubjectService.normalize_subject_name(name),
                code=code,
                normalized_code=SubjectService.normalize_subject_code(code),
                description=description,
                is_active=True,
            )
            session.add(subject)
            await session.flush()
        subjects.append(subject)
    return subjects


async def ensure_classes(session, tenant: Tenant, profile: SchoolProfile) -> list[ClassRoom]:
    classes: list[ClassRoom] = []
    previous_by_arm: dict[str, ClassRoom] = {}

    for class_name in profile.class_names:
        for arm in profile.arms:
            from app.core.utils.normalization import normalized_class_arm_key, normalized_class_name_key
            norm_name = normalized_class_name_key(class_name)
            norm_arm = normalized_class_arm_key(arm)
            classroom = (
                await session.execute(
                    select(ClassRoom).where(
                        ClassRoom.tenant_id == tenant.id,
                        ClassRoom.normalized_name == norm_name,
                        ClassRoom.normalized_arm == norm_arm,
                    )
                )
            ).scalar_one_or_none()

            if classroom is None:
                from app.core.utils.normalization import normalized_class_arm_key, normalized_class_name_key
                classroom = ClassRoom(
                    tenant_id=tenant.id,
                    name=class_name,
                    normalized_name=normalized_class_name_key(class_name),
                    arm=arm,
                    normalized_arm=normalized_class_arm_key(arm),
                    is_active=True,
                    is_terminal=class_name == profile.class_names[-1] and class_name == "SS 3",
                )
                session.add(classroom)
                await session.flush()

            previous = previous_by_arm.get(arm)
            if previous is not None:
                previous.next_class_id = classroom.id
            previous_by_arm[arm] = classroom
            classes.append(classroom)

    await session.flush()
    return classes


async def create_students(
    session,
    tenant: Tenant,
    profile: SchoolProfile,
    classes: list[ClassRoom],
    seed_value: int,
) -> int:
    rng = random.Random(seed_value)
    local_fake = Faker("en_NG")
    local_fake.seed_instance(seed_value)
    password_hash = hash_password(DEFAULT_PASSWORD)
    created = 0

    for index in range(1, profile.student_count + 1):
        number = admission_number(profile, index)
        exists = (
            await session.execute(
                select(Student.id).where(
                    Student.tenant_id == tenant.id,
                    Student.admission_number == number,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue

        classroom = classes[rng.randrange(len(classes))]
        gender = Gender.MALE if rng.random() < 0.51 else Gender.FEMALE
        first_name = (
            local_fake.first_name_male()
            if gender == Gender.MALE
            else local_fake.first_name_female()
        )
        academic_status, is_active = student_status(index, rng)
        birth_year = rng.randint(2008, 2016)

        student = Student(
            tenant_id=tenant.id,
            admission_number=number,
            password_hash=password_hash,
            first_name=first_name,
            last_name=local_fake.last_name(),
            account_status=(
                StudentAccountStatus.ACTIVE
                if is_active
                else StudentAccountStatus.INACTIVE
            ),
            is_verified=rng.random() > 0.04,
            is_active=is_active,
            password_reset_required=index % 13 == 0,
            date_of_birth=date(
                birth_year,
                rng.randint(1, 12),
                rng.randint(1, 28),
            ),
            gender=gender,
            state_of_origin=local_fake.state(),
            class_id=classroom.id if academic_status not in {AcademicStatus.GRADUATED, AcademicStatus.WITHDRAWN, AcademicStatus.EXPELLED} else None,
            arm=classroom.arm if academic_status not in {AcademicStatus.GRADUATED, AcademicStatus.WITHDRAWN, AcademicStatus.EXPELLED} else None,
            status=academic_status,
            profile_status=(
                StudentProfileStatus.INCOMPLETE
                if index % 17 == 0
                else StudentProfileStatus.COMPLETE
            ),
            graduation_date=(
                date(2026, 7, 20)
                if academic_status == AcademicStatus.GRADUATED
                else None
            ),
        )
        session.add(student)
        await session.flush()

        session.add(
            AuthIdentity(
                tenant_id=tenant.id,
                identifier=number,
                identifier_type=IdentifierType.ADMISSION_NUMBER,
                actor_type=ActorType.STUDENT,
                actor_id=student.id,
                is_active=is_active,
            )
        )
        created += 1

        if created % 100 == 0:
            await session.flush()

    await session.flush()
    return created


async def seed_all(reset: bool, seed_value: int) -> None:
    configure_mappers()
    Faker.seed(seed_value)
    random.seed(seed_value)

    async with AsyncSessionLocal() as session:
        if reset:
            await purge_demo_data(session)

        summaries: list[tuple[str, int, int, int]] = []
        for school_index, profile in enumerate(SCHOOL_PROFILES, start=1):
            print(f"\n[{school_index}/{len(SCHOOL_PROFILES)}] Seeding {profile.school_name}...")
            tenant = await ensure_tenant(session, profile)
            subjects = await ensure_subjects(session, tenant, profile)
            classes = await ensure_classes(session, tenant, profile)
            students = await create_students(
                session,
                tenant,
                profile,
                classes,
                seed_value + school_index * 1000,
            )
            await session.commit()
            summaries.append((profile.school_name, len(subjects), len(classes), students))
            print(
                f"Created/verified {len(subjects)} subjects, "
                f"{len(classes)} classes and {students} students."
            )

        print("\nDemo seed complete")
        print("-" * 78)
        for school_name, subject_count, class_count, student_count in summaries:
            print(
                f"{school_name:<38} "
                f"subjects={subject_count:<2} classes={class_count:<2} students={student_count}"
            )
        print("-" * 78)
        print(f"Generic student password: {DEFAULT_PASSWORD}")
        print("Run again with --reset to remove and regenerate only these five demo schools.")

    await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create five sparse, distinct demo schools using the current Weave schema."
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and recreate only the five schools generated by this script.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed_all(args.reset, args.seed))
