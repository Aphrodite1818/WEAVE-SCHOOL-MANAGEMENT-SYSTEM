#!/usr/bin/env python3
"""Seed two live-like Weave schools into the configured PostgreSQL database.

Run from the backend directory:
    uv run python scripts/seed_live_demo.py --reset

Remote/staging database:
    WEAVE_SEED_CONFIRM=SEED_WEAVE_DEMO \
      uv run python scripts/seed_live_demo.py --reset --allow-remote

All generated accounts use password: Test12345
All generated email accounts are aliases of: taiwoayimora623@gmail.com
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from faker import Faker
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.database import AsyncSessionLocal, engine
from app.config.security import hash_auth_secret, hash_password
from app.config.settings import settings
from app.core.utils.normalization import normalized_class_arm_key, normalized_class_name_key
import app.models  # noqa: F401
from app.modules.announcements.models import (
    Announcement,
    AnnouncementActorType,
    AnnouncementCategory,
    AnnouncementPriority,
    AnnouncementRead,
    AnnouncementReadStatus,
    AnnouncementRecipientRole,
    AnnouncementStatus,
    AnnouncementTarget,
    AnnouncementTargetType,
)
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import (
    ParentAccount,
    ParentAccountStatus,
    ParentInvitation,
    ParentInvitationStatus,
    ParentMembership,
    ParentMembershipStatus,
)
from app.modules.report_cards.models import ReportCard, ReportCardStatus, ReportCardSubjectLine
from app.modules.student_academics.models import (
    AcademicResultStatus,
    AcademicSession,
    AcademicSessionStatus,
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
    ParentLinkVerifiedByType,
    ParentRelationship,
    Student,
    StudentAccountStatus,
    StudentEnrollment,
    StudentEnrollmentOutcome,
    StudentParentLink,
    StudentParentLinkRequest,
    StudentParentLinkRequestStatus,
    StudentParentLinkStatus,
    StudentProfileStatus,
)
from app.modules.subjects.models import Subject
from app.modules.subscriptions.models import PaymentTransaction, TenantSubscription
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    PaymentStatus,
    SubscriptionStatus,
)
from app.modules.teachers.models import (
    TeacherAccount,
    TeacherAccountStatus,
    TeacherInvitation,
    TeacherInvitationStatus,
    TeacherMembership,
    TeacherMembershipStatus,
    TeacherMembershipSubject,
)
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.shared.base_model import Base
from app.tenant_management.models import (
    SubscriptionPlan,
    Tenant,
    TenantStatus,
    TenantVerificationStatus,
)

PASSWORD = "Test12345"
BASE_EMAIL = "taiwoayimora623@gmail.com"
ALIAS_MARKER = "weave-demo"
REMOTE_CONFIRMATION = "SEED_WEAVE_DEMO"
DEFAULT_STUDENTS = 550
DEFAULT_TEACHERS = 30
DEFAULT_SEED = 20260725
CHUNK_SIZE = 1000


@dataclass(frozen=True, slots=True)
class SchoolSpec:
    name: str
    slug: str
    city: str
    state: str
    address: str


SCHOOLS = (
    SchoolSpec(
        name="Aurora Crest Academy",
        slug="aurora-crest-demo",
        city="Ikeja",
        state="Lagos",
        address="18 Sunrise Avenue, Ikeja, Lagos",
    ),
    SchoolSpec(
        name="Meridian Heights College",
        slug="meridian-heights-demo",
        city="Abuja",
        state="FCT",
        address="42 Unity Crescent, Gwarinpa, Abuja",
    ),
)

SUBJECTS = (
    ("English Language", "ENG", True),
    ("Mathematics", "MTH", True),
    ("Civic Education", "CIV", True),
    ("Computer Studies", "CMP", True),
    ("Social Studies", "SOS", True),
    ("Basic Science", "BSC", True),
    ("Business Studies", "BUS", False),
    ("Agricultural Science", "AGR", False),
    ("Biology", "BIO", False),
    ("Chemistry", "CHM", False),
    ("Physics", "PHY", False),
    ("Economics", "ECO", False),
)

CLASS_SEQUENCE = ("JSS 1", "JSS 2", "JSS 3", "SS 1", "SS 2", "SS 3")
CLASS_ARMS = ("A", "B")
NIGERIAN_STATES = (
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Benue",
    "Borno", "Cross River", "Delta", "Edo", "Ekiti", "Enugu", "FCT",
    "Imo", "Kaduna", "Kano", "Katsina", "Kogi", "Kwara", "Lagos",
    "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers",
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


def environment_name() -> str:
    raw = getattr(settings, "ENV", "")
    return str(getattr(raw, "value", raw)).strip().lower()


def alias_email(label: str) -> str:
    local, domain = BASE_EMAIL.split("@", 1)
    safe = re.sub(r"[^a-z0-9-]+", "-", label.casefold()).strip("-")
    return f"{local}+{ALIAS_MARKER}-{safe}@{domain}"


def prefix_from_name(name: str) -> str:
    ignored = {"the", "of", "and", "school"}
    words = [w for w in re.findall(r"[A-Za-z0-9]+", name) if w.casefold() not in ignored]
    return ("".join(w[0] for w in words).upper() or "SCH")[:5]


def random_phone(fake: Faker) -> str:
    digits = re.sub(r"\D", "", fake.msisdn())
    return f"+234{digits[-10:]}"


def chunks(rows: Sequence[dict[str, Any]], size: int = CHUNK_SIZE):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


async def bulk_insert(session: AsyncSession, model: Any, rows: Sequence[dict[str, Any]]) -> None:
    for batch in chunks(rows):
        if batch:
            await session.execute(insert(model), list(batch))


def score_grade(total: Decimal) -> tuple[str, str]:
    if total >= 70:
        return "A", "Excellent"
    if total >= 60:
        return "B", "Very Good"
    if total >= 50:
        return "C", "Good"
    if total >= 45:
        return "D", "Fair"
    if total >= 40:
        return "E", "Pass"
    return "F", "Needs Improvement"


def subject_codes_for_class(class_name: str) -> set[str]:
    common = {"ENG", "MTH", "CIV", "CMP", "SOS", "BSC"}
    return common | ({"BUS", "AGR"} if class_name.startswith("JSS") else {"BIO", "CHM", "PHY", "ECO"})


def age_range(class_name: str) -> tuple[int, int]:
    return {
        "JSS 1": (10, 13), "JSS 2": (11, 14), "JSS 3": (12, 15),
        "SS 1": (13, 16), "SS 2": (14, 17), "SS 3": (15, 19),
    }[class_name]


def fake_birth_date(rng: random.Random, class_name: str) -> date:
    youngest, oldest = age_range(class_name)
    age = rng.randint(youngest, oldest)
    today = date.today()
    start = date(today.year - age - 1, 8, 1)
    end = date(today.year - age, 7, 31)
    return start + timedelta(days=rng.randint(0, max((end - start).days, 1)))


def previous_class(class_name: str) -> str | None:
    index = CLASS_SEQUENCE.index(class_name)
    return CLASS_SEQUENCE[index - 1] if index else None


def lifecycle_for(index: int) -> str:
    if index <= 5:
        return "suspended"
    if index <= 9:
        return "withdrawn"
    if index <= 11:
        return "expelled"
    if index <= 15:
        return "graduated"
    if index <= 20:
        return "archived"
    if index <= 25:
        return "promotion_hold"
    return "active"


def identity_row(
    *, identifier: str, identifier_type: IdentifierType, actor_type: ActorType,
    actor_id: uuid.UUID, tenant_id: uuid.UUID | None, active: bool = True,
) -> dict[str, Any]:
    normalized = identifier.casefold() if identifier_type == IdentifierType.EMAIL else identifier.upper()
    return {
        "id": new_id(), "tenant_id": tenant_id, "identifier": normalized,
        "identifier_type": identifier_type, "actor_type": actor_type,
        "actor_id": actor_id, "is_active": active,
    }


def teacher_account_row(
    account_id: uuid.UUID, email: str, fake: Faker, password_hash_value: str,
    first_name: str | None = None, last_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": account_id, "email": email.casefold(), "password_hash": password_hash_value,
        "first_name": first_name or fake.first_name(), "last_name": last_name or fake.last_name(),
        "phone_number": random_phone(fake),
        "qualification": random.choice(["B.Ed", "B.Sc (Ed)", "M.Ed", "PGDE", "B.A (Ed)"]),
        "specialization": random.choice([
            "Mathematics Education", "English Education", "Science Education",
            "Social Sciences", "Educational Technology",
        ]),
        "passport_photo_url": None, "account_status": TeacherAccountStatus.ACTIVE,
        "is_verified": True, "is_active": True,
        "last_login_at": now_utc() - timedelta(days=random.randint(0, 12)),
    }


def parent_account_row(
    account_id: uuid.UUID, email: str, fake: Faker, password_hash_value: str,
    first_name: str | None = None, last_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": account_id, "email": email.casefold(), "password_hash": password_hash_value,
        "first_name": first_name or fake.first_name(), "last_name": last_name or fake.last_name(),
        "phone_number": random_phone(fake),
        "occupation": random.choice([
            "Engineer", "Teacher", "Accountant", "Entrepreneur", "Civil Servant",
            "Nurse", "Lawyer", "Designer",
        ]),
        "address": fake.address().replace("\n", ", "), "emergency_phone": random_phone(fake),
        "account_status": ParentAccountStatus.ACTIVE, "is_verified": True, "is_active": True,
        "last_login_at": now_utc() - timedelta(days=random.randint(0, 15)),
    }


def remote_database() -> bool:
    parsed = urlparse(str(settings.DATABASE_URL or "").replace("+asyncpg", ""))
    return (parsed.hostname or "").casefold() not in {"", "localhost", "127.0.0.1", "::1"}


def enforce_safety(args: argparse.Namespace) -> None:
    if environment_name() in {"prod", "production"} and not args.allow_production:
        raise RuntimeError("Refusing to seed production. Use a disposable staging database.")
    if remote_database():
        if not args.allow_remote:
            raise RuntimeError("DATABASE_URL is remote. Re-run with --allow-remote for staging only.")
        if os.getenv("WEAVE_SEED_CONFIRM") != REMOTE_CONFIRMATION:
            raise RuntimeError(f"Remote seeding requires WEAVE_SEED_CONFIRM={REMOTE_CONFIRMATION}.")


async def cleanup_demo(session: AsyncSession) -> None:
    tenant_ids = list((await session.execute(
        select(Tenant.id).where(Tenant.slug.in_([s.slug for s in SCHOOLS]))
    )).scalars())

    if tenant_ids:
        classes_table = Base.metadata.tables.get("public.classes")
        sessions_table = Base.metadata.tables.get("public.academic_sessions")
        if classes_table is not None:
            await session.execute(update(classes_table).where(classes_table.c.tenant_id.in_(tenant_ids)).values(next_class_id=None))
        if sessions_table is not None:
            await session.execute(update(sessions_table).where(sessions_table.c.tenant_id.in_(tenant_ids)).values(next_academic_session_id=None))

        for table in reversed(Base.metadata.sorted_tables):
            if table.name == "tenants" or "tenant_id" not in table.c:
                continue
            await session.execute(delete(table).where(table.c.tenant_id.in_(tenant_ids)))
        await session.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))

    local, domain = BASE_EMAIL.split("@", 1)
    pattern = f"{local}+{ALIAS_MARKER}-%@{domain}"
    await session.execute(delete(AuthIdentity).where(AuthIdentity.identifier.like(pattern)))
    await session.execute(delete(TeacherAccount).where(TeacherAccount.email.like(pattern)))
    await session.execute(delete(ParentAccount).where(ParentAccount.email.like(pattern)))


async def seed_shared_accounts(
    session: AsyncSession, fake: Faker, password_hash_value: str,
    credentials: dict[str, Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    teacher_id, parent_id = new_id(), new_id()
    teacher_email, parent_email = alias_email("shared-teacher"), alias_email("shared-parent")
    await bulk_insert(session, TeacherAccount, [teacher_account_row(
        teacher_id, teacher_email, fake, password_hash_value, "Taiwo", "Shared Teacher"
    )])
    await bulk_insert(session, ParentAccount, [parent_account_row(
        parent_id, parent_email, fake, password_hash_value, "Taiwo", "Shared Parent"
    )])
    await bulk_insert(session, AuthIdentity, [
        identity_row(identifier=teacher_email, identifier_type=IdentifierType.EMAIL,
                     actor_type=ActorType.TEACHER_ACCOUNT, actor_id=teacher_id, tenant_id=None),
        identity_row(identifier=parent_email, identifier_type=IdentifierType.EMAIL,
                     actor_type=ActorType.PARENT_ACCOUNT, actor_id=parent_id, tenant_id=None),
    ])
    credentials["shared_accounts"] = {
        "teacher": {"email": teacher_email, "password": PASSWORD},
        "parent": {"email": parent_email, "password": PASSWORD},
    }
    return teacher_id, parent_id


async def seed_school(
    session: AsyncSession,
    *,
    spec: SchoolSpec,
    fake: Faker,
    rng: random.Random,
    students_per_school: int,
    teachers_per_school: int,
    password_hash_value: str,
    shared_teacher_account_id: uuid.UUID,
    shared_parent_account_id: uuid.UUID,
    credentials: dict[str, Any],
    include_results: bool,
    include_report_cards: bool,
) -> dict[str, int]:
    now, today = now_utc(), date.today()
    prefix, key, tenant_id = prefix_from_name(spec.name), prefix_from_name(spec.name).casefold(), new_id()
    count: dict[str, int] = defaultdict(int)
    school_credentials: dict[str, Any] = {
        "name": spec.name, "slug": spec.slug, "prefix": prefix,
        "tenant_admins": [], "teachers": [], "parents": [], "students": [],
        "pending_teacher_invitations": [], "pending_parent_invitations": [],
        "pending_parent_link_requests": [],
    }
    credentials["schools"].append(school_credentials)

    await bulk_insert(session, Tenant, [{
        "id": tenant_id, "school_name": spec.name, "slug": spec.slug,
        "admission_number_prefix": prefix, "school_bot_whatssap_number": None,
        "email": alias_email(f"{key}-school"), "phone": random_phone(fake),
        "address": spec.address, "city": spec.city, "state": spec.state,
        "country": "Nigeria", "logo_url": None, "status": TenantStatus.ACTIVE,
        "plan": SubscriptionPlan.ENTERPRISE, "trial_ends_at": None,
        "subscription_ends_at": now + timedelta(days=365), "is_deleted": False,
        "deleted_at": None, "max_students": 1000, "max_teachers": 100,
        "feature_flags": {
            "student_management": True, "teacher_management": True,
            "parent_portal": True, "academic_setup": True,
            "report_cards": True, "announcements": True,
            "advanced_analytics": True, "bulk_import": True,
        },
        "timezone": "Africa/Lagos", "language": "en",
        "onboarding_completed": True, "branches": [spec.city],
        "verification_status": TenantVerificationStatus.ACTIVE,
    }])
    count["tenants"] += 1

    subscription_id = new_id()
    period_start, period_end = now - timedelta(days=10), now + timedelta(days=20)
    await bulk_insert(session, TenantSubscription, [{
        "id": subscription_id, "tenant_id": tenant_id,
        "plan_code": SubscriptionPlan.ENTERPRISE, "status": SubscriptionStatus.ACTIVE,
        "billing_interval": BillingInterval.MONTHLY, "provider": PaymentProvider.MANUAL,
        "current_period_start": period_start, "current_period_end": period_end,
        "trial_ends_at": None, "grace_ends_at": None, "cancel_at_period_end": False,
        "cancelled_at": None, "expired_at": None, "is_current": True,
        "provider_customer_code": f"CUS-{prefix}-DEMO",
        "provider_subscription_code": f"SUB-{prefix}-DEMO",
        "provider_email_token": None, "last_payment_reference": f"MANUAL-{prefix}-006",
        "last_payment_at": period_start, "next_payment_at": period_end,
        "metadata_json": {"seed": ALIAS_MARKER, "school": spec.name},
        "notes": "Live-like demo subscription generated by seed_live_demo.py",
    }])
    count["subscriptions"] += 1

    payments = []
    for index in range(1, 7):
        payments.append({
            "id": new_id(), "tenant_id": tenant_id, "subscription_id": subscription_id,
            "provider": PaymentProvider.MANUAL, "status": PaymentStatus.SUCCESS,
            "reference": f"MANUAL-{prefix}-{index:03d}", "provider_transaction_id": None,
            "plan_code": SubscriptionPlan.ENTERPRISE,
            "billing_interval": BillingInterval.MONTHLY,
            "amount": Decimal("80000.00"), "amount_kobo": 8_000_000, "currency": "NGN",
            "authorization_url": None, "access_code": None,
            "paid_at": now - timedelta(days=30 * (6 - index) + 10),
            "failure_reason": None, "raw_payload": {"seed": ALIAS_MARKER, "method": "manual"},
        })
    payments.append({
        "id": new_id(), "tenant_id": tenant_id, "subscription_id": subscription_id,
        "provider": PaymentProvider.PAYSTACK, "status": PaymentStatus.FAILED,
        "reference": f"PAYSTACK-{prefix}-FAILED-001", "provider_transaction_id": None,
        "plan_code": SubscriptionPlan.ENTERPRISE,
        "billing_interval": BillingInterval.MONTHLY,
        "amount": Decimal("80000.00"), "amount_kobo": 8_000_000, "currency": "NGN",
        "authorization_url": None, "access_code": None, "paid_at": None,
        "failure_reason": "Demo failed transaction",
        "raw_payload": {"seed": ALIAS_MARKER, "status": "failed"},
    })
    await bulk_insert(session, PaymentTransaction, payments)
    count["payment_transactions"] += len(payments)

    admin_rows, admin_identities, admin_ids = [], [], []
    for index in range(1, 3):
        admin_id, email = new_id(), alias_email(f"{key}-admin-{index:02d}")
        admin_ids.append(admin_id)
        admin_rows.append({
            "id": admin_id, "tenant_id": tenant_id, "email": email,
            "password_hash": password_hash_value, "passport_photo_url": None,
            "account_status": TenantAdminStatus.ACTIVE, "is_verified": True,
            "is_active": True, "last_login_at": now - timedelta(days=index - 1),
        })
        admin_identities.append(identity_row(
            identifier=email, identifier_type=IdentifierType.EMAIL,
            actor_type=ActorType.TENANT_ADMIN, actor_id=admin_id, tenant_id=tenant_id,
        ))
        school_credentials["tenant_admins"].append({"email": email, "password": PASSWORD})
    await bulk_insert(session, TenantAdmin, admin_rows)
    await bulk_insert(session, AuthIdentity, admin_identities)
    count["tenant_admins"] += len(admin_rows)
    count["auth_identities"] += len(admin_identities)
    primary_admin_id = admin_ids[0]

    previous_session_id, current_session_id = new_id(), new_id()
    closed_at = datetime(2025, 7, 31, 16, tzinfo=timezone.utc)
    await bulk_insert(session, AcademicSession, [
        {
            "id": previous_session_id, "tenant_id": tenant_id, "name": "2024/2025",
            "start_date": date(2024, 9, 16), "end_date": date(2025, 7, 31),
            "status": AcademicSessionStatus.CLOSED, "is_current": False, "is_active": False,
            "closing_started_at": closed_at - timedelta(days=1), "closed_at": closed_at,
            "closed_by_admin_id": primary_admin_id,
            "next_academic_session_id": None,
        },
        {
            "id": current_session_id, "tenant_id": tenant_id, "name": "2025/2026",
            "start_date": date(2025, 9, 15), "end_date": date(2026, 7, 31),
            "status": AcademicSessionStatus.OPEN, "is_current": True, "is_active": True,
            "closing_started_at": None, "closed_at": None,
            "closed_by_admin_id": None, "next_academic_session_id": None,
        },
    ])
    await session.execute(
        update(AcademicSession)
        .where(AcademicSession.id == previous_session_id)
        .values(next_academic_session_id=current_session_id)
    )
    count["academic_sessions"] += 2

    current_ranges = {
        AcademicTermName.FIRST_TERM: (date(2025, 9, 15), date(2025, 12, 12)),
        AcademicTermName.SECOND_TERM: (date(2026, 1, 12), date(2026, 4, 2)),
        AcademicTermName.THIRD_TERM: (date(2026, 4, 20), date(2026, 7, 31)),
    }
    previous_ranges = {
        AcademicTermName.FIRST_TERM: (date(2024, 9, 16), date(2024, 12, 13)),
        AcademicTermName.SECOND_TERM: (date(2025, 1, 13), date(2025, 4, 4)),
        AcademicTermName.THIRD_TERM: (date(2025, 4, 22), date(2025, 7, 31)),
    }
    term_rows, current_term_ids = [], {}
    for term_name in AcademicTermName:
        previous_id, current_id = new_id(), new_id()
        current_term_ids[term_name] = current_id
        p_start, p_end = previous_ranges[term_name]
        c_start, c_end = current_ranges[term_name]
        term_rows.extend([
            {
                "id": previous_id, "tenant_id": tenant_id,
                "academic_session_id": previous_session_id, "name": term_name,
                "start_date": p_start, "end_date": p_end,
                "is_current": False, "is_active": False,
            },
            {
                "id": current_id, "tenant_id": tenant_id,
                "academic_session_id": current_session_id, "name": term_name,
                "start_date": c_start, "end_date": c_end,
                "is_current": term_name == AcademicTermName.THIRD_TERM,
                "is_active": term_name == AcademicTermName.THIRD_TERM,
            },
        ])
    await bulk_insert(session, AcademicTerm, term_rows)
    count["academic_terms"] += len(term_rows)
    current_term_id = current_term_ids[AcademicTermName.THIRD_TERM]

    scales = [
        ("A", "70.00", "100.00", "Excellent"),
        ("B", "60.00", "69.99", "Very Good"),
        ("C", "50.00", "59.99", "Good"),
        ("D", "45.00", "49.99", "Fair"),
        ("E", "40.00", "44.99", "Pass"),
        ("F", "0.00", "39.99", "Needs Improvement"),
    ]
    await bulk_insert(session, GradingScale, [{
        "id": new_id(), "tenant_id": tenant_id, "grade": grade,
        "min_score": Decimal(low), "max_score": Decimal(high),
        "remark": remark, "is_active": True,
    } for grade, low, high, remark in scales])
    count["grading_scales"] += len(scales)

    teacher_accounts, memberships, teacher_identities = [], [], []
    teacher_membership_ids, active_teacher_ids = [], []
    teacher_name_by_membership: dict[uuid.UUID, str] = {}

    shared_membership_id = new_id()
    teacher_membership_ids.append(shared_membership_id)
    active_teacher_ids.append(shared_membership_id)
    teacher_name_by_membership[shared_membership_id] = "Taiwo Shared Teacher"
    memberships.append({
        "id": shared_membership_id, "tenant_id": tenant_id,
        "teacher_account_id": shared_teacher_account_id,
        "staff_id": f"{prefix}-T-000", "job_title": "Senior Mathematics Teacher",
        "department": "Sciences", "employment_type": "Full-time",
        "status": TeacherMembershipStatus.ACTIVE,
        "joined_at": now - timedelta(days=600), "ended_at": None, "end_reason": None,
        "receive_email_notifications": True, "receive_push_notifications": True,
    })
    school_credentials["teachers"].append({
        "email": alias_email("shared-teacher"), "password": PASSWORD,
        "staff_id": f"{prefix}-T-000", "shared_across_schools": True,
    })

    for index in range(1, teachers_per_school):
        account_id, membership_id = new_id(), new_id()
        email = alias_email(f"{key}-teacher-{index:03d}")
        first_name, last_name = fake.first_name(), fake.last_name()
        if index == teachers_per_school - 1:
            membership_status, ended_at, reason = (
                TeacherMembershipStatus.INACTIVE, now - timedelta(days=45),
                "Demo historical teacher offboarding",
            )
        elif index in {teachers_per_school - 2, teachers_per_school - 3}:
            membership_status, ended_at, reason = TeacherMembershipStatus.SUSPENDED, None, None
        else:
            membership_status, ended_at, reason = TeacherMembershipStatus.ACTIVE, None, None
            active_teacher_ids.append(membership_id)
        teacher_accounts.append(teacher_account_row(
            account_id, email, fake, password_hash_value, first_name, last_name
        ))
        memberships.append({
            "id": membership_id, "tenant_id": tenant_id,
            "teacher_account_id": account_id, "staff_id": f"{prefix}-T-{index:03d}",
            "job_title": random.choice([
                "Subject Teacher", "Senior Subject Teacher", "Class Teacher", "Academic Coordinator"
            ]),
            "department": random.choice(["Sciences", "Languages", "Humanities", "Technology"]),
            "employment_type": random.choice(["Full-time", "Part-time"]),
            "status": membership_status, "joined_at": now - timedelta(days=rng.randint(180, 1200)),
            "ended_at": ended_at, "end_reason": reason,
            "receive_email_notifications": True, "receive_push_notifications": rng.random() > 0.2,
        })
        teacher_identities.append(identity_row(
            identifier=email, identifier_type=IdentifierType.EMAIL,
            actor_type=ActorType.TEACHER_ACCOUNT, actor_id=account_id, tenant_id=None,
        ))
        teacher_membership_ids.append(membership_id)
        teacher_name_by_membership[membership_id] = f"{first_name} {last_name}"
        school_credentials["teachers"].append({
            "email": email, "password": PASSWORD, "staff_id": f"{prefix}-T-{index:03d}",
            "membership_status": membership_status.value,
        })
    await bulk_insert(session, TeacherAccount, teacher_accounts)
    await bulk_insert(session, TeacherMembership, memberships)
    await bulk_insert(session, AuthIdentity, teacher_identities)
    count["teacher_accounts"] += len(teacher_accounts) + 1
    count["teacher_memberships"] += len(memberships)
    count["auth_identities"] += len(teacher_identities)

    subject_rows, subject_by_code = [], {}
    for name, code, core in SUBJECTS:
        subject_id = new_id()
        row = {
            "id": subject_id, "tenant_id": tenant_id, "name": name,
            "normalized_name": " ".join(name.casefold().split()), "code": code,
            "normalized_code": code.casefold(),
            "description": f"{name} curriculum for {spec.name}.", "is_active": True,
        }
        subject_rows.append(row)
        subject_by_code[code] = {"id": subject_id, "name": name, "code": code, "core": core}
    await bulk_insert(session, Subject, subject_rows)
    count["subjects"] += len(subject_rows)

    class_rows, class_by_key = [], {}
    for arm in CLASS_ARMS:
        ids = {name: new_id() for name in CLASS_SEQUENCE}
        for class_index, class_name in enumerate(CLASS_SEQUENCE):
            next_name = CLASS_SEQUENCE[class_index + 1] if class_index + 1 < len(CLASS_SEQUENCE) else None
            head_id = active_teacher_ids[(class_index * len(CLASS_ARMS) + CLASS_ARMS.index(arm)) % len(active_teacher_ids)]
            row = {
                "id": ids[class_name], "tenant_id": tenant_id, "name": class_name,
                "normalized_name": normalized_class_name_key(class_name), "arm": arm,
                "normalized_arm": normalized_class_arm_key(arm), "is_active": True,
                "teacher_membership_id": head_id,
                "next_class_id": None,
                "is_terminal": class_name == "SS 3",
            }
            class_rows.append(row)
            class_by_key[(class_name, arm)] = {
                **row,
                "planned_next_class_id": ids[next_name] if next_name else None,
            }
    await bulk_insert(session, ClassRoom, class_rows)
    for class_record in class_by_key.values():
        if class_record["planned_next_class_id"] is not None:
            await session.execute(
                update(ClassRoom)
                .where(ClassRoom.id == class_record["id"])
                .values(next_class_id=class_record["planned_next_class_id"])
            )
    count["classes"] += len(class_rows)

    subject_teacher_pool = {}
    for subject_index, (_, code, _) in enumerate(SUBJECTS):
        subject_teacher_pool[code] = [
            active_teacher_ids[(subject_index * 2 + offset) % len(active_teacher_ids)]
            for offset in range(2)
        ]

    class_subject_rows, assignment_rows, legacy_rows = [], [], []
    capability_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    teaching_map: dict[tuple[uuid.UUID, uuid.UUID], dict[str, Any]] = {}
    for class_index, class_row in enumerate(class_rows):
        allowed = subject_codes_for_class(class_row["name"])
        sort_order = 0
        for name, code, core in SUBJECTS:
            if code not in allowed:
                continue
            subject = subject_by_code[code]
            teacher_id = subject_teacher_pool[code][class_index % 2]
            class_subject_id, assignment_id, legacy_id = new_id(), new_id(), new_id()
            sort_order += 1
            class_subject_rows.append({
                "id": class_subject_id, "tenant_id": tenant_id,
                "class_id": class_row["id"], "subject_id": subject["id"],
                "is_core": core, "is_active": True,
            })
            assignment_rows.append({
                "id": assignment_id, "tenant_id": tenant_id,
                "class_subject_id": class_subject_id,
                "teacher_membership_id": teacher_id, "is_active": True,
                "effective_from": date(2025, 9, 15), "effective_to": None,
            })
            legacy_rows.append({
                "id": legacy_id, "tenant_id": tenant_id,
                "class_id": class_row["id"], "subject_id": subject["id"],
                "teacher_membership_id": teacher_id, "is_core": core,
                "sort_order": sort_order, "is_active": True,
            })
            capability_pairs.add((teacher_id, subject["id"]))
            teaching_map[(class_row["id"], subject["id"])] = {
                "class_subject_id": class_subject_id,
                "teacher_assignment_id": assignment_id,
                "class_subject_teacher_id": legacy_id,
                "teacher_membership_id": teacher_id,
                "subject_name": name, "subject_code": code,
            }

    for index, teacher_id in enumerate(active_teacher_ids):
        capability_pairs.add((teacher_id, subject_rows[index % len(subject_rows)]["id"]))
    capabilities = [{
        "id": new_id(), "tenant_id": tenant_id,
        "teacher_membership_id": teacher_id, "subject_id": subject_id,
        "is_active": True,
    } for teacher_id, subject_id in sorted(capability_pairs, key=lambda p: (str(p[0]), str(p[1])))]
    await bulk_insert(session, TeacherMembershipSubject, capabilities)
    await bulk_insert(session, ClassSubject, class_subject_rows)
    await bulk_insert(session, TeacherAssignment, assignment_rows)
    await bulk_insert(session, ClassSubjectTeacher, legacy_rows)
    count["teacher_capabilities"] += len(capabilities)
    count["class_subjects"] += len(class_subject_rows)
    count["teacher_assignments"] += len(assignment_rows)
    count["legacy_teacher_assignments"] += len(legacy_rows)

    student_rows, student_identities, enrollment_rows, students = [], [], [], []
    for index in range(1, students_per_school + 1):
        lifecycle = lifecycle_for(index)
        class_row = class_rows[(index - 1) % len(class_rows)]
        if lifecycle == "graduated":
            class_row = class_by_key[("SS 3", CLASS_ARMS[index % 2])]
        gender = Gender.MALE if index % 2 else Gender.FEMALE
        first_name = fake.first_name_male() if gender == Gender.MALE else fake.first_name_female()
        last_name = fake.last_name()
        student_id = new_id()
        admission_number = f"{prefix}/2026/{index:04d}"
        terminal = lifecycle in {"withdrawn", "expelled", "graduated"}
        archived = lifecycle == "archived"
        suspended = lifecycle == "suspended"

        if lifecycle == "withdrawn":
            academic_status, outcome = AcademicStatus.WITHDRAWN, StudentEnrollmentOutcome.WITHDRAWN
        elif lifecycle == "expelled":
            academic_status, outcome = AcademicStatus.EXPELLED, StudentEnrollmentOutcome.EXPELLED
        elif lifecycle == "graduated":
            academic_status, outcome = AcademicStatus.GRADUATED, StudentEnrollmentOutcome.GRADUATED
        elif suspended:
            academic_status, outcome = AcademicStatus.SUSPENDED, StudentEnrollmentOutcome.ENROLLED
        else:
            academic_status, outcome = AcademicStatus.ACTIVE, StudentEnrollmentOutcome.ENROLLED

        login_active = not (terminal or archived or suspended)
        student_rows.append({
            "id": student_id, "tenant_id": tenant_id,
            "admission_number": admission_number, "password_hash": password_hash_value,
            "first_name": first_name, "last_name": last_name,
            "account_status": StudentAccountStatus.ACTIVE if login_active else StudentAccountStatus.INACTIVE,
            "is_verified": True, "is_active": login_active, "password_reset_required": False,
            "last_login_at": now - timedelta(days=rng.randint(0, 30)) if login_active else None,
            "date_of_birth": fake_birth_date(rng, class_row["name"]), "gender": gender,
            "state_of_origin": rng.choice(NIGERIAN_STATES), "passport_photo_url": None,
            "admission_date": date(2025 - min(CLASS_SEQUENCE.index(class_row["name"]), 4), 9, rng.randint(10, 25)),
            "graduation_date": today - timedelta(days=30) if lifecycle == "graduated" else None,
            "class_id": None if terminal else class_row["id"],
            "arm": None if terminal else class_row["arm"],
            "status": academic_status, "promotion_hold": lifecycle == "promotion_hold",
            "is_archived": archived,
            "archived_at": now - timedelta(days=20) if archived else None,
            "archived_by_admin_id": primary_admin_id if archived else None,
            "archive_reason": "Demo archived student" if archived else None,
            "profile_status": StudentProfileStatus.COMPLETE,
        })
        student_identities.append(identity_row(
            identifier=admission_number, identifier_type=IdentifierType.ADMISSION_NUMBER,
            actor_type=ActorType.STUDENT, actor_id=student_id,
            tenant_id=tenant_id, active=login_active,
        ))

        old_name = previous_class(class_row["name"])
        if old_name and index % 3:
            old_class = class_by_key[(old_name, class_row["arm"])]
            enrollment_rows.append({
                "id": new_id(), "tenant_id": tenant_id, "student_id": student_id,
                "class_id": old_class["id"], "academic_session_id": previous_session_id,
                "started_on": date(2024, 9, 16), "ended_on": date(2025, 7, 31),
                "is_current": False, "outcome": StudentEnrollmentOutcome.PROMOTED,
                "reason": "Promoted into current class", "changed_by_admin_id": primary_admin_id,
            })
        if terminal:
            enrollment_rows.append({
                "id": new_id(), "tenant_id": tenant_id, "student_id": student_id,
                "class_id": class_row["id"], "academic_session_id": current_session_id,
                "started_on": date(2025, 9, 15), "ended_on": today - timedelta(days=30),
                "is_current": False, "outcome": outcome,
                "reason": f"Demo {lifecycle} lifecycle record",
                "changed_by_admin_id": primary_admin_id,
            })
        else:
            enrollment_rows.append({
                "id": new_id(), "tenant_id": tenant_id, "student_id": student_id,
                "class_id": class_row["id"], "academic_session_id": current_session_id,
                "started_on": date(2025, 9, 15), "ended_on": None,
                "is_current": True, "outcome": StudentEnrollmentOutcome.ENROLLED,
                "reason": None, "changed_by_admin_id": primary_admin_id,
            })

        students.append({
            "id": student_id, "admission_number": admission_number,
            "first_name": first_name, "last_name": last_name,
            "class_id": None if terminal else class_row["id"],
            "source_class_id": class_row["id"], "class_name": class_row["name"],
            "arm": class_row["arm"], "lifecycle": lifecycle,
            "eligible_for_results": not terminal,
        })
        school_credentials["students"].append({
            "admission_number": admission_number, "password": PASSWORD,
            "name": f"{first_name} {last_name}",
            "class": f"{class_row['name']} {class_row['arm']}", "lifecycle": lifecycle,
        })

    await bulk_insert(session, Student, student_rows)
    await bulk_insert(session, AuthIdentity, student_identities)
    await bulk_insert(session, StudentEnrollment, enrollment_rows)
    count["students"] += len(student_rows)
    count["auth_identities"] += len(student_identities)
    count["student_enrollments"] += len(enrollment_rows)

    parent_accounts, parent_membership_rows, parent_identities = [], [], []
    parent_links, parent_memberships = [], []
    shared_parent_membership_id = new_id()
    parent_membership_rows.append({
        "id": shared_parent_membership_id, "tenant_id": tenant_id,
        "parent_account_id": shared_parent_account_id,
        "status": ParentMembershipStatus.ACTIVE,
        "joined_at": now - timedelta(days=450), "ended_at": None, "end_reason": None,
        "receive_email_notifications": True, "receive_push_notifications": True,
    })
    school_credentials["parents"].append({
        "email": alias_email("shared-parent"), "password": PASSWORD,
        "shared_across_schools": True,
    })

    parent_count = (students_per_school + 1) // 2
    for index in range(1, parent_count + 1):
        account_id, membership_id = new_id(), new_id()
        email = alias_email(f"{key}-parent-{index:04d}")
        first_name, last_name = fake.first_name(), fake.last_name()
        inactive = index == parent_count
        parent_accounts.append(parent_account_row(
            account_id, email, fake, password_hash_value, first_name, last_name
        ))
        parent_membership_rows.append({
            "id": membership_id, "tenant_id": tenant_id,
            "parent_account_id": account_id,
            "status": ParentMembershipStatus.INACTIVE if inactive else ParentMembershipStatus.ACTIVE,
            "joined_at": now - timedelta(days=rng.randint(90, 900)),
            "ended_at": now - timedelta(days=30) if inactive else None,
            "end_reason": "Demo inactive parent membership" if inactive else None,
            "receive_email_notifications": True,
            "receive_push_notifications": rng.random() > 0.25,
        })
        parent_identities.append(identity_row(
            identifier=email, identifier_type=IdentifierType.EMAIL,
            actor_type=ActorType.PARENT_ACCOUNT, actor_id=account_id, tenant_id=None,
        ))
        parent_memberships.append({"id": membership_id, "inactive": inactive, "email": email})
        school_credentials["parents"].append({
            "email": email, "password": PASSWORD,
            "membership_status": ParentMembershipStatus.INACTIVE.value if inactive else ParentMembershipStatus.ACTIVE.value,
        })

    usable_parents = [item for item in parent_memberships if not item["inactive"]]
    for index, student in enumerate(students):
        membership = usable_parents[(index // 2) % len(usable_parents)]
        if student["lifecycle"] in {"withdrawn", "expelled"}:
            link_status = StudentParentLinkStatus.ENDED
        elif student["lifecycle"] == "graduated":
            link_status = StudentParentLinkStatus.ALUMNI_READ_ONLY
        else:
            link_status = StudentParentLinkStatus.ACTIVE
        parent_links.append({
            "id": new_id(), "tenant_id": tenant_id, "student_id": student["id"],
            "parent_membership_id": membership["id"],
            "relationship_type": ParentRelationship.MOTHER if index % 2 == 0 else ParentRelationship.FATHER,
            "status": link_status,
            "is_primary_contact": link_status != StudentParentLinkStatus.ENDED,
            "receives_academic_updates": True, "receives_fee_updates": True,
            "verified_at": now - timedelta(days=rng.randint(30, 600)),
            "verified_by_type": ParentLinkVerifiedByType.SYSTEM, "verified_by_id": None,
            "ended_at": now - timedelta(days=30) if link_status == StudentParentLinkStatus.ENDED else None,
            "end_reason": "Student is no longer active" if link_status == StudentParentLinkStatus.ENDED else None,
        })
        if index % 7 == 0:
            second = usable_parents[(index // 2 + 1) % len(usable_parents)]
            if second["id"] != membership["id"]:
                parent_links.append({
                    "id": new_id(), "tenant_id": tenant_id, "student_id": student["id"],
                    "parent_membership_id": second["id"],
                    "relationship_type": ParentRelationship.GUARDIAN,
                    "status": link_status, "is_primary_contact": False,
                    "receives_academic_updates": True, "receives_fee_updates": False,
                    "verified_at": now - timedelta(days=rng.randint(20, 500)),
                    "verified_by_type": ParentLinkVerifiedByType.TENANT_ADMIN,
                    "verified_by_id": primary_admin_id,
                    "ended_at": now - timedelta(days=30) if link_status == StudentParentLinkStatus.ENDED else None,
                    "end_reason": "Student is no longer active" if link_status == StudentParentLinkStatus.ENDED else None,
                })

    first_active = next(s for s in students if s["lifecycle"] == "active")
    parent_links.append({
        "id": new_id(), "tenant_id": tenant_id, "student_id": first_active["id"],
        "parent_membership_id": shared_parent_membership_id,
        "relationship_type": ParentRelationship.GUARDIAN,
        "status": StudentParentLinkStatus.ACTIVE, "is_primary_contact": False,
        "receives_academic_updates": True, "receives_fee_updates": True,
        "verified_at": now - timedelta(days=120),
        "verified_by_type": ParentLinkVerifiedByType.TENANT_ADMIN,
        "verified_by_id": primary_admin_id, "ended_at": None, "end_reason": None,
    })
    inactive_membership = parent_memberships[-1]
    lifecycle_student = next(s for s in students if s["lifecycle"] == "active" and s["id"] != first_active["id"])
    parent_links.append({
        "id": new_id(), "tenant_id": tenant_id, "student_id": lifecycle_student["id"],
        "parent_membership_id": inactive_membership["id"],
        "relationship_type": ParentRelationship.SPONSOR,
        "status": StudentParentLinkStatus.ENDED, "is_primary_contact": False,
        "receives_academic_updates": False, "receives_fee_updates": False,
        "verified_at": now - timedelta(days=250),
        "verified_by_type": ParentLinkVerifiedByType.TENANT_ADMIN,
        "verified_by_id": primary_admin_id,
        "ended_at": now - timedelta(days=30), "end_reason": "Demo ended child link",
    })

    await bulk_insert(session, ParentAccount, parent_accounts)
    await bulk_insert(session, ParentMembership, parent_membership_rows)
    await bulk_insert(session, AuthIdentity, parent_identities)
    await bulk_insert(session, StudentParentLink, parent_links)
    count["parent_accounts"] += len(parent_accounts) + 1
    count["parent_memberships"] += len(parent_membership_rows)
    count["auth_identities"] += len(parent_identities)
    count["student_parent_links"] += len(parent_links)

    teacher_invites = []
    for index in range(1, 6):
        raw_token = f"{ALIAS_MARKER}-{prefix}-teacher-{index}-{uuid.uuid4().hex}"
        email = alias_email(f"{key}-pending-teacher-{index:02d}")
        teacher_invites.append({
            "id": new_id(), "tenant_id": tenant_id, "invited_email": email,
            "token_digest": hash_auth_secret(raw_token),
            "staff_id": f"{prefix}-PENDING-{index:02d}", "job_title": "Subject Teacher",
            "department": "Academics", "employment_type": "Full-time",
            "status": TeacherInvitationStatus.PENDING,
            "expires_at": now + timedelta(days=7), "accepted_at": None,
            "revoked_at": None, "created_by_admin_id": primary_admin_id,
            "accepted_by_teacher_account_id": None,
        })
        school_credentials["pending_teacher_invitations"].append({
            "email": email, "raw_token": raw_token,
            "expires_at": (now + timedelta(days=7)).isoformat(),
        })
    await bulk_insert(session, TeacherInvitation, teacher_invites)
    count["teacher_invitations"] += len(teacher_invites)

    invite_students = [s for s in students if s["lifecycle"] == "active"][10:20]
    parent_invites = []
    for index, student in enumerate(invite_students[:5], 1):
        raw_token = f"{ALIAS_MARKER}-{prefix}-parent-{index}-{uuid.uuid4().hex}"
        email = alias_email(f"{key}-pending-parent-{index:02d}")
        parent_invites.append({
            "id": new_id(), "tenant_id": tenant_id, "student_id": student["id"],
            "invited_email": email, "relationship_type": ParentRelationship.GUARDIAN,
            "admission_number_snapshot": student["admission_number"],
            "token_digest": hash_auth_secret(raw_token),
            "status": ParentInvitationStatus.PENDING,
            "expires_at": now + timedelta(days=7), "accepted_at": None,
            "revoked_at": None, "created_by_admin_id": primary_admin_id,
            "accepted_by_parent_account_id": None,
        })
        school_credentials["pending_parent_invitations"].append({
            "email": email, "student_admission_number": student["admission_number"],
            "raw_token": raw_token, "expires_at": (now + timedelta(days=7)).isoformat(),
        })
    await bulk_insert(session, ParentInvitation, parent_invites)
    count["parent_invitations"] += len(parent_invites)

    approval_accounts, approval_memberships, approval_identities = [], [], []
    approval_invitations, approval_requests = [], []
    for index, student in enumerate(invite_students[5:10], 1):
        account_id, membership_id, invitation_id, request_id = new_id(), new_id(), new_id(), new_id()
        email = alias_email(f"{key}-approval-parent-{index:02d}")
        raw_token = f"{ALIAS_MARKER}-{prefix}-approval-{index}-{uuid.uuid4().hex}"
        approval_accounts.append(parent_account_row(account_id, email, fake, password_hash_value))
        approval_memberships.append({
            "id": membership_id, "tenant_id": tenant_id, "parent_account_id": account_id,
            "status": ParentMembershipStatus.ACTIVE, "joined_at": now - timedelta(days=2),
            "ended_at": None, "end_reason": None,
            "receive_email_notifications": True, "receive_push_notifications": True,
        })
        approval_identities.append(identity_row(
            identifier=email, identifier_type=IdentifierType.EMAIL,
            actor_type=ActorType.PARENT_ACCOUNT, actor_id=account_id, tenant_id=None,
        ))
        approval_invitations.append({
            "id": invitation_id, "tenant_id": tenant_id, "student_id": student["id"],
            "invited_email": email, "relationship_type": ParentRelationship.GUARDIAN,
            "admission_number_snapshot": student["admission_number"],
            "token_digest": hash_auth_secret(raw_token),
            "status": ParentInvitationStatus.ACCEPTED,
            "expires_at": now + timedelta(days=5), "accepted_at": now - timedelta(days=1),
            "revoked_at": None, "created_by_admin_id": primary_admin_id,
            "accepted_by_parent_account_id": account_id,
        })
        approval_requests.append({
            "id": request_id, "tenant_id": tenant_id, "invitation_id": invitation_id,
            "student_id": student["id"], "parent_account_id": account_id,
            "parent_membership_id": membership_id,
            "admission_number_snapshot": student["admission_number"],
            "relationship_type": ParentRelationship.GUARDIAN,
            "status": StudentParentLinkRequestStatus.PENDING,
            "requested_at": now - timedelta(hours=index), "responded_at": None,
            "responded_by_type": None, "responded_by_id": None, "rejection_reason": None,
        })
        school_credentials["pending_parent_link_requests"].append({
            "email": email, "password": PASSWORD,
            "student_admission_number": student["admission_number"],
            "request_id": str(request_id),
        })
    await bulk_insert(session, ParentAccount, approval_accounts)
    await bulk_insert(session, ParentMembership, approval_memberships)
    await bulk_insert(session, AuthIdentity, approval_identities)
    await bulk_insert(session, ParentInvitation, approval_invitations)
    await bulk_insert(session, StudentParentLinkRequest, approval_requests)
    count["parent_accounts"] += len(approval_accounts)
    count["parent_memberships"] += len(approval_memberships)
    count["auth_identities"] += len(approval_identities)
    count["parent_invitations"] += len(approval_invitations)
    count["parent_link_requests"] += len(approval_requests)

    result_rows: list[dict[str, Any]] = []
    results_by_student: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
    if include_results:
        by_class: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
        for (class_id, subject_id), mapping in teaching_map.items():
            by_class[class_id].append({"subject_id": subject_id, **mapping})
        for student in students:
            if not student["eligible_for_results"] or student["class_id"] is None:
                continue
            for mapping in by_class[student["class_id"]]:
                test_score = Decimal(rng.randint(8, 20))
                assessment_score = Decimal(rng.randint(8, 20))
                exam_score = Decimal(rng.randint(24, 60))
                total_score = test_score + assessment_score + exam_score
                grade, remark = score_grade(total_score)
                result_id = new_id()
                row = {
                    "id": result_id, "tenant_id": tenant_id,
                    "student_id": student["id"], "class_id": student["class_id"],
                    "subject_id": mapping["subject_id"],
                    "teacher_membership_id": mapping["teacher_membership_id"],
                    "class_subject_teacher_id": mapping["class_subject_teacher_id"],
                    "teacher_assignment_id": mapping["teacher_assignment_id"],
                    "academic_session_id": current_session_id,
                    "academic_term_id": current_term_id,
                    "test_score": test_score, "assessment_score": assessment_score,
                    "exam_score": exam_score, "total_score": total_score,
                    "grade": grade, "remark": remark,
                    "status": AcademicResultStatus.SUBMITTED,
                    "recorded_by_actor_type": "teacher",
                    "recorded_by_actor_id": mapping["teacher_membership_id"],
                }
                result_rows.append(row)
                results_by_student[student["id"]].append({
                    **row,
                    "subject_name": mapping["subject_name"],
                    "subject_code": mapping["subject_code"],
                    "teacher_name": teacher_name_by_membership[mapping["teacher_membership_id"]],
                })
        await bulk_insert(session, StudentSubjectResult, result_rows)
        count["student_subject_results"] += len(result_rows)

    if include_results and include_report_cards:
        class_averages: dict[uuid.UUID, list[tuple[uuid.UUID, Decimal]]] = defaultdict(list)
        averages: dict[uuid.UUID, Decimal] = {}
        for student_id, rows in results_by_student.items():
            average = (sum(r["total_score"] for r in rows) / Decimal(len(rows))).quantize(Decimal("0.01"))
            averages[student_id] = average
            class_averages[rows[0]["class_id"]].append((student_id, average))
        positions: dict[uuid.UUID, tuple[int, int]] = {}
        for values in class_averages.values():
            values.sort(key=lambda item: item[1], reverse=True)
            for position, (student_id, _) in enumerate(values, 1):
                positions[student_id] = (position, len(values))

        cards, lines = [], []
        for student in students:
            result_lines = results_by_student.get(student["id"])
            if not result_lines:
                continue
            card_id = new_id()
            average = averages[student["id"]]
            position, out_of = positions[student["id"]]
            published = student["id"].int % 5 != 0
            cards.append({
                "id": card_id, "tenant_id": tenant_id,
                "student_id": student["id"], "class_id": result_lines[0]["class_id"],
                "academic_session_id": current_session_id,
                "academic_term_id": current_term_id,
                "total_score": sum(r["total_score"] for r in result_lines),
                "average_score": average, "position": position, "position_out_of": out_of,
                "class_teacher_comment": (
                    "A strong term. Continue building consistency."
                    if average >= 60 else "Good effort. More focused revision is recommended."
                ),
                "principal_comment": "Excellent progress." if average >= 70 else "Keep working steadily.",
                "version": 1, "published_at": now - timedelta(days=2) if published else None,
                "published_by": primary_admin_id if published else None,
                "is_outdated": False, "superseded_at": None,
                "status": ReportCardStatus.PUBLISHED if published else ReportCardStatus.DRAFT,
                "generated_by_actor_type": "tenant_admin",
                "generated_by_actor_id": primary_admin_id,
            })
            for result in result_lines:
                lines.append({
                    "id": new_id(), "tenant_id": tenant_id, "report_card_id": card_id,
                    "student_subject_result_id": result["id"], "subject_id": result["subject_id"],
                    "subject_name": result["subject_name"], "subject_code": result["subject_code"],
                    "teacher_name": result["teacher_name"],
                    "test_score": result["test_score"],
                    "assessment_score": result["assessment_score"],
                    "exam_score": result["exam_score"], "total_score": result["total_score"],
                    "grade": result["grade"], "remark": result["remark"],
                })
        await bulk_insert(session, ReportCard, cards)
        await bulk_insert(session, ReportCardSubjectLine, lines)
        count["report_cards"] += len(cards)
        count["report_card_subject_lines"] += len(lines)

    templates = [
        ("Welcome to the third term", "The third term is underway. Review the calendar and assessment dates.", AnnouncementCategory.ACADEMIC, AnnouncementPriority.NORMAL, AnnouncementTargetType.ALL, None),
        ("Continuous assessment schedule", "Continuous assessments will run next week.", AnnouncementCategory.EXAMINATION, AnnouncementPriority.HIGH, AnnouncementTargetType.ROLE, AnnouncementRecipientRole.STUDENT),
        ("Parent engagement meeting", "Parents are invited to the term engagement meeting on Saturday at 10:00 AM.", AnnouncementCategory.EVENT, AnnouncementPriority.NORMAL, AnnouncementTargetType.ROLE, AnnouncementRecipientRole.PARENT),
        ("Staff coordination notice", "Teaching staff should submit result-entry progress before Friday.", AnnouncementCategory.SYSTEM, AnnouncementPriority.HIGH, AnnouncementTargetType.ROLE, AnnouncementRecipientRole.TEACHER),
        ("School fee reminder", "Outstanding balances should be resolved through the approved process.", AnnouncementCategory.FINANCE, AnnouncementPriority.NORMAL, AnnouncementTargetType.ALL, None),
        ("Health and safety update", "Students should bring personal water bottles.", AnnouncementCategory.HEALTH, AnnouncementPriority.NORMAL, AnnouncementTargetType.ALL, None),
        ("Emergency drill", "A routine emergency preparedness drill will hold this week.", AnnouncementCategory.EMERGENCY, AnnouncementPriority.URGENT, AnnouncementTargetType.ALL, None),
        ("Inter-house sports registration", "Registration for inter-house sporting events is now open.", AnnouncementCategory.SPORTS, AnnouncementPriority.LOW, AnnouncementTargetType.ALL, None),
        ("Class attendance follow-up", "Class teachers should review attendance exceptions.", AnnouncementCategory.ATTENDANCE, AnnouncementPriority.HIGH, AnnouncementTargetType.ROLE, AnnouncementRecipientRole.TEACHER),
        ("Holiday notice", "The final holiday schedule will be communicated after examinations.", AnnouncementCategory.HOLIDAY, AnnouncementPriority.NORMAL, AnnouncementTargetType.ALL, None),
    ]
    announcement_rows, target_rows, read_rows = [], [], []
    for index, (title, body, category, priority, target_type, role) in enumerate(templates, 1):
        announcement_id = new_id()
        status = AnnouncementStatus.DRAFT if index == len(templates) else AnnouncementStatus.PUBLISHED
        announcement_rows.append({
            "id": announcement_id, "tenant_id": tenant_id,
            "title": f"{prefix}: {title}", "body": body,
            "category": category, "priority": priority, "status": status,
            "created_by_actor_type": AnnouncementActorType.TENANT_ADMIN,
            "created_by_actor_id": primary_admin_id,
            "publish_at": now - timedelta(days=index) if status == AnnouncementStatus.PUBLISHED else None,
            "expires_at": now + timedelta(days=60), "is_pinned": index in {1, 7},
        })
        target_rows.append({
            "id": new_id(), "tenant_id": tenant_id,
            "announcement_id": announcement_id, "target_type": target_type,
            "role": role, "class_id": None, "student_id": None,
            "parent_membership_id": None, "teacher_membership_id": None,
        })
        if status == AnnouncementStatus.PUBLISHED and index <= 3:
            sample_student = next(s for s in students if s["eligible_for_results"])
            read_rows.append({
                "id": new_id(), "tenant_id": tenant_id,
                "announcement_id": announcement_id,
                "actor_type": AnnouncementRecipientRole.STUDENT,
                "actor_id": sample_student["id"], "status": AnnouncementReadStatus.READ,
                "read_at": now - timedelta(hours=index), "acknowledged_at": None,
            })

    class_announcement_id = new_id()
    target_class = class_by_key[("JSS 1", "A")]
    announcement_rows.append({
        "id": class_announcement_id, "tenant_id": tenant_id,
        "title": f"{prefix}: JSS 1A Mathematics assignment",
        "body": "Complete exercises 1-20 before the next Mathematics lesson.",
        "category": AnnouncementCategory.ASSIGNMENT,
        "priority": AnnouncementPriority.NORMAL,
        "status": AnnouncementStatus.PUBLISHED,
        "created_by_actor_type": AnnouncementActorType.TEACHER,
        "created_by_actor_id": target_class["teacher_membership_id"],
        "publish_at": now - timedelta(days=1), "expires_at": now + timedelta(days=14),
        "is_pinned": False,
    })
    target_rows.append({
        "id": new_id(), "tenant_id": tenant_id,
        "announcement_id": class_announcement_id,
        "target_type": AnnouncementTargetType.CLASS, "role": None,
        "class_id": target_class["id"], "student_id": None,
        "parent_membership_id": None, "teacher_membership_id": None,
    })
    await bulk_insert(session, Announcement, announcement_rows)
    await bulk_insert(session, AnnouncementTarget, target_rows)
    await bulk_insert(session, AnnouncementRead, read_rows)
    count["announcements"] += len(announcement_rows)
    count["announcement_targets"] += len(target_rows)
    count["announcement_reads"] += len(read_rows)

    school_credentials["summary"] = dict(count)
    return dict(count)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed two live-like Weave schools.")
    parser.add_argument("--students-per-school", type=int, default=DEFAULT_STUDENTS)
    parser.add_argument("--teachers-per-school", type=int, default=DEFAULT_TEACHERS)
    parser.add_argument("--random-seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--reset", action="store_true", help="Replace only the two demo tenants and demo aliases.")
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--without-results", action="store_true")
    parser.add_argument("--without-report-cards", action="store_true")
    parser.add_argument("--credentials-output", default="weave_demo_credentials.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 500 <= args.students_per_school <= 600:
        parser.error("--students-per-school must be between 500 and 600")
    if args.teachers_per_school < 20:
        parser.error("--teachers-per-school must be at least 20")
    return args


async def main() -> None:
    args = arguments()
    enforce_safety(args)
    

    if args.dry_run:
        print(json.dumps({
            "schools": len(SCHOOLS),
            "students_per_school": args.students_per_school,
            "teachers_per_school": args.teachers_per_school,
            "students_total": len(SCHOOLS) * args.students_per_school,
            "password": PASSWORD,
            "base_email": BASE_EMAIL,
            "environment": environment_name(),
            "remote_database": remote_database(),
        }, indent=2))
        await engine.dispose()
        return

    try:
        fake = Faker("en_NG")
    except Exception:
        fake = Faker("en_US")
    Faker.seed(args.random_seed)
    random.seed(args.random_seed)
    rng = random.Random(args.random_seed)
    password_hash_value = hash_password(PASSWORD)
    credentials: dict[str, Any] = {
        "generated_at": now_utc().isoformat(),
        "password_for_all_accounts": PASSWORD,
        "base_email": BASE_EMAIL,
        "alias_marker": ALIAS_MARKER,
        "shared_accounts": {},
        "schools": [],
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            existing_ids = list((await session.execute(
                select(Tenant.id).where(Tenant.slug.in_([s.slug for s in SCHOOLS]))
            )).scalars())
            if existing_ids and not args.reset:
                raise RuntimeError("Demo tenants already exist. Re-run with --reset.")
            if args.reset:
                await cleanup_demo(session)

            shared_teacher_id, shared_parent_id = await seed_shared_accounts(
                session, fake, password_hash_value, credentials
            )
            totals: dict[str, int] = defaultdict(int)
            for school_index, spec in enumerate(SCHOOLS):
                Faker.seed(args.random_seed + school_index)
                school_counts = await seed_school(
                    session,
                    spec=spec,
                    fake=fake,
                    rng=rng,
                    students_per_school=args.students_per_school,
                    teachers_per_school=args.teachers_per_school,
                    password_hash_value=password_hash_value,
                    shared_teacher_account_id=shared_teacher_id,
                    shared_parent_account_id=shared_parent_id,
                    credentials=credentials,
                    include_results=not args.without_results,
                    include_report_cards=not args.without_results and not args.without_report_cards,
                )
                for key, value in school_counts.items():
                    totals[key] += value
            credentials["total_summary"] = dict(totals)

    output = Path(args.credentials_output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(credentials, indent=2, default=str), encoding="utf-8")
    await engine.dispose()

    print("\nWeave demo data seeded successfully.")
    print(f"Schools: {len(SCHOOLS)}")
    print(f"Students: {len(SCHOOLS) * args.students_per_school}")
    print(f"Generic password: {PASSWORD}")
    print(f"Credentials: {output}")
    print("\nPrimary tenant-admin logins:")
    for school in credentials["schools"]:
        admin = school["tenant_admins"][0]
        print(f"  {school['name']}: {admin['email']} / {PASSWORD}")
    print("\nCross-school accounts:")
    print(f"  Teacher: {credentials['shared_accounts']['teacher']['email']} / {PASSWORD}")
    print(f"  Parent: {credentials['shared_accounts']['parent']['email']} / {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
