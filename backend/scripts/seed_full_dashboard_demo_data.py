from __future__ import annotations

"""Create five realistic Weave schools by reusing the existing single-school seeder.

Place in ``backend/scripts/seed_realistic_multi_school.py`` and run:

    python scripts/seed_realistic_multi_school.py \
        --base-seeder scripts/seed_full_dashboard_data.py \
        --reset --seed 20260727

The generated data is intentionally uneven: different school sizes, incomplete
results, mixed result lifecycle states, missing report cards, draft/published
cards, and a small number of non-active students.
"""

import argparse
import asyncio
import importlib.util
import logging
import random
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

from faker import Faker
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.database import AsyncSessionLocal, engine
from app.config.security import hash_password
from app.core.utils.normalization import normalize_email
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.report_cards.models import ReportCard, ReportCardStatus
from app.modules.student_academics.models import AcademicResultStatus, StudentSubjectResult
from app.modules.students.models import Student
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.tenant_management.models import (
    SubscriptionPlan,
    Tenant,
    TenantStatus,
    TenantVerificationStatus,
)

DEFAULT_PASSWORD = "Test12345!"
BASE_EMAIL = "taiwoayimora623@gmail.com"
fake = Faker("en_NG")


@dataclass(frozen=True)
class SchoolProfile:
    name: str
    slug: str
    prefix: str
    city: str
    state: str
    students: int
    teachers: int
    parents: int
    initial_drafts: int
    result_coverage: float
    report_card_coverage: float
    published_card_ratio: float


SCHOOLS = (
    SchoolProfile("Cedar Grove College", "cedar-grove-college", "CGC", "Ikeja", "Lagos", 620, 68, 410, 125, 0.88, 0.76, 0.72),
    SchoolProfile("Bluecrest Academy", "bluecrest-academy", "BCA", "Lekki", "Lagos", 360, 44, 245, 70, 0.81, 0.69, 0.61),
    SchoolProfile("Unity Heights Secondary School", "unity-heights-secondary", "UHS", "Ibadan", "Oyo", 780, 82, 520, 180, 0.91, 0.82, 0.78),
    SchoolProfile("New Dawn International School", "new-dawn-international", "NDI", "Abuja", "FCT", 245, 31, 165, 55, 0.72, 0.57, 0.48),
    SchoolProfile("Royal Heritage College", "royal-heritage-college", "RHC", "Abeokuta", "Ogun", 495, 55, 330, 95, 0.84, 0.73, 0.66),
)


def aliased_email(tag: str) -> str:
    local, domain = BASE_EMAIL.split("@", 1)
    return f"{local}+{tag}@{domain}"


def load_base_seeder(path: Path) -> ModuleType:
    if not path.exists():
        raise FileNotFoundError(f"Base seeder was not found: {path}")
    spec = importlib.util.spec_from_file_location("weave_base_seeder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load base seeder from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "seed_full_dashboard_data"):
        raise AttributeError("Base seeder must expose async seed_full_dashboard_data(...).")
    return module


def enum_member(enum_cls, *names):
    if enum_cls is None:
        return None
    for name in names:
        member = getattr(enum_cls, name, None)
        if member is not None:
            return member
    return None


async def get_or_create_school(session, profile: SchoolProfile, index: int) -> tuple[Tenant, TenantAdmin]:
    tenant = (await session.execute(select(Tenant).where(Tenant.slug == profile.slug))).scalar_one_or_none()
    school_email = aliased_email(f"school-{index}")
    admin_email = normalize_email(aliased_email(f"admin-{index}"))

    if tenant is None:
        tenant = Tenant(
            school_name=profile.name,
            slug=profile.slug,
            admission_number_prefix=profile.prefix,
            email=school_email,
            phone=fake.phone_number()[:20],
            address=fake.address().replace("\n", ", "),
            city=profile.city,
            state=profile.state,
            country="Nigeria",
            status=TenantStatus.TRIAL,
            plan=SubscriptionPlan.FREE_TRIAL,
            trial_ends_at=datetime.now(UTC) + timedelta(days=90),
            max_students=max(profile.students + 250, 1000),
            max_teachers=max(profile.teachers + 50, 150),
            feature_flags={"realistic_seed": True, "whatsapp_bot": index % 2 == 0},
            timezone="Africa/Lagos",
            language="en",
            onboarding_completed=True,
            verification_status=TenantVerificationStatus.ACTIVE,
            branches=["Main Campus", "Junior Campus"] if index in {1, 3} else ["Main Campus"],
        )
        session.add(tenant)
        await session.flush()
    else:
        tenant.status = TenantStatus.TRIAL
        tenant.verification_status = TenantVerificationStatus.ACTIVE
        tenant.onboarding_completed = True
        tenant.max_students = max(profile.students + 250, 1000)
        tenant.max_teachers = max(profile.teachers + 50, 150)

    admin = (await session.execute(select(TenantAdmin).where(
        TenantAdmin.tenant_id == tenant.id,
        TenantAdmin.email == admin_email,
    ))).scalar_one_or_none()

    if admin is None:
        admin = TenantAdmin(
            tenant_id=tenant.id,
            email=admin_email,
            password_hash=hash_password(DEFAULT_PASSWORD),
            account_status=TenantAdminStatus.ACTIVE,
            is_verified=True,
            is_active=True,
        )
        session.add(admin)
        await session.flush()
        session.add(AuthIdentity(
            tenant_id=tenant.id,
            identifier=admin_email,
            identifier_type=IdentifierType.EMAIL,
            actor_type=ActorType.TENANT_ADMIN,
            actor_id=admin.id,
            is_active=True,
        ))
    else:
        admin.password_hash = hash_password(DEFAULT_PASSWORD)
        admin.account_status = TenantAdminStatus.ACTIVE
        admin.is_verified = True
        admin.is_active = True

    await session.commit()
    return tenant, admin


async def make_results_sparse(session, tenant_id: uuid.UUID, coverage: float) -> dict[str, int]:
    rows = list((await session.execute(
        select(StudentSubjectResult)
        .where(StudentSubjectResult.tenant_id == tenant_id)
        .order_by(StudentSubjectResult.student_id, StudentSubjectResult.subject_id)
    )).scalars().all())

    by_student: dict[uuid.UUID, list[StudentSubjectResult]] = {}
    for row in rows:
        by_student.setdefault(row.student_id, []).append(row)

    draft = enum_member(AcademicResultStatus, "DRAFT")
    submitted = enum_member(AcademicResultStatus, "SUBMITTED")
    approved = enum_member(AcademicResultStatus, "APPROVED")
    locked = enum_member(AcademicResultStatus, "LOCKED")
    counts = {"removed": 0, "partial_drafts": 0, "draft": 0, "submitted": 0, "approved": 0, "locked": 0}

    for student_rows in by_student.values():
        if random.random() > coverage:
            for row in student_rows:
                await session.delete(row)
                counts["removed"] += 1
            continue

        random.shuffle(student_rows)
        keep_count = max(1, round(len(student_rows) * random.uniform(0.55, 1.0)))
        for row in student_rows[keep_count:]:
            await session.delete(row)
            counts["removed"] += 1

        for row in student_rows[:keep_count]:
            roll = random.random()
            if roll < 0.24 and draft is not None:
                row.status = draft
                counts["draft"] += 1
                pattern = random.choice(("exam", "assessment_exam", "test_exam", "all"))
                if pattern in {"exam", "assessment_exam", "test_exam", "all"}:
                    row.exam_score = None
                if pattern in {"assessment_exam", "all"}:
                    row.assessment_score = None
                if pattern in {"test_exam", "all"}:
                    row.test_score = None
                row.total_score = None
                row.grade = None
                row.remark = None
                counts["partial_drafts"] += 1
            elif roll < 0.49 and submitted is not None:
                row.status = submitted
                counts["submitted"] += 1
            elif roll < 0.69 and approved is not None:
                row.status = approved
                counts["approved"] += 1
            elif locked is not None:
                row.status = locked
                counts["locked"] += 1
            elif submitted is not None:
                row.status = submitted
                counts["submitted"] += 1

    await session.commit()
    return counts


async def make_report_cards_sparse(session, tenant_id: uuid.UUID, coverage: float, published_ratio: float) -> dict[str, int]:
    cards = list((await session.execute(select(ReportCard).where(ReportCard.tenant_id == tenant_id))).scalars().all())
    published = enum_member(ReportCardStatus, "PUBLISHED")
    draft = enum_member(ReportCardStatus, "DRAFT")
    archived = enum_member(ReportCardStatus, "ARCHIVED")
    counts = {"removed": 0, "draft": 0, "published": 0, "archived": 0}

    for card in cards:
        if random.random() > coverage:
            await session.delete(card)
            counts["removed"] += 1
            continue
        roll = random.random()
        if roll < published_ratio and published is not None:
            card.status = published
            card.published_at = card.published_at or datetime.now(UTC)
            counts["published"] += 1
        elif roll < 0.96 and draft is not None:
            card.status = draft
            card.published_at = None
            if hasattr(card, "published_by"):
                card.published_by = None
            counts["draft"] += 1
        elif archived is not None:
            card.status = archived
            counts["archived"] += 1
        elif draft is not None:
            card.status = draft
            counts["draft"] += 1

    await session.commit()
    return counts


async def vary_student_lifecycle(session, tenant_id: uuid.UUID) -> dict[str, int]:
    students = list((await session.execute(select(Student).where(Student.tenant_id == tenant_id))).scalars().all())
    status_enum = type(students[0].status) if students else None
    active = enum_member(status_enum, "ACTIVE")
    suspended = enum_member(status_enum, "SUSPENDED")
    withdrawn = enum_member(status_enum, "WITHDRAWN")
    counts = {"active": 0, "suspended": 0, "withdrawn": 0}

    for student in students:
        roll = random.random()
        if roll < 0.018 and suspended is not None:
            student.status = suspended
            counts["suspended"] += 1
        elif roll < 0.032 and withdrawn is not None:
            student.status = withdrawn
            student.is_active = False
            counts["withdrawn"] += 1
        else:
            if active is not None:
                student.status = active
            counts["active"] += 1

    await session.commit()
    return counts


async def seed_school(base_seeder: ModuleType, profile: SchoolProfile, index: int, reset: bool, seed: int) -> dict:
    async with AsyncSessionLocal() as session:
        tenant, admin = await get_or_create_school(session, profile, index)
        tenant_id = tenant.id
        admin_email = admin.email

    await base_seeder.seed_full_dashboard_data(
        tenant_id_arg=str(tenant_id),
        draft_results=profile.initial_drafts,
        num_students=profile.students,
        num_teachers=profile.teachers,
        num_parents=profile.parents,
        reset=reset,
        faker_seed=seed + index,
    )

    async with AsyncSessionLocal() as session:
        result_counts = await make_results_sparse(session, tenant_id, profile.result_coverage)
        card_counts = await make_report_cards_sparse(session, tenant_id, profile.report_card_coverage, profile.published_card_ratio)
        lifecycle_counts = await vary_student_lifecycle(session, tenant_id)

    return {
        "school": profile.name,
        "tenant_id": str(tenant_id),
        "admin_email": admin_email,
        "students": profile.students,
        "results": result_counts,
        "report_cards": card_counts,
        "student_lifecycle": lifecycle_counts,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed five realistic Weave schools.")
    parser.add_argument("--base-seeder", type=Path, required=True, help="Path to your existing single-school Faker seeder.")
    parser.add_argument("--reset", action="store_true", help="Reset prior rows generated by the base seeder.")
    parser.add_argument("--seed", type=int, default=20260727)
    args = parser.parse_args()

    Faker.seed(args.seed)
    random.seed(args.seed)
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    base_seeder = load_base_seeder(args.base_seeder.resolve())

    summaries = []
    for index, profile in enumerate(SCHOOLS, start=1):
        print(f"\n[{index}/{len(SCHOOLS)}] Seeding {profile.name}...")
        summaries.append(await seed_school(base_seeder, profile, index, args.reset, args.seed))

    print("\n" + "=" * 72)
    print("REALISTIC MULTI-SCHOOL SEED COMPLETE")
    print("=" * 72)
    print(f"Generic password: {DEFAULT_PASSWORD}")
    for item in summaries:
        print(f"\n{item['school']}")
        print(f"  Tenant ID: {item['tenant_id']}")
        print(f"  Admin: {item['admin_email']}")
        print(f"  Students requested: {item['students']}")
        print(f"  Results: {item['results']}")
        print(f"  Report cards: {item['report_cards']}")
        print(f"  Student lifecycle: {item['student_lifecycle']}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
