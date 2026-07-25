from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from faker import Faker
from sqlalchemy import Select, delete, select, update

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
    normalize_staff_id,
    normalize_subject_code,
    normalize_subject_name,
    normalized_class_arm_key,
    normalized_class_name_key,
)
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import AuthService
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.report_cards.models import ReportCard, ReportCardStatus, ReportCardSubjectLine
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
from app.modules.teachers.models import Teacher, TeacherAccountStatus, TeacherStatus, TeacherSubject
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.models import Tenant, TenantStatus, TenantVerificationStatus


DEFAULT_PASSWORD = "Test12345!"
DECIMAL_PLACES = Decimal("0.01")

# Tags used to mark rows created by this bulk Faker seeder, so a --reset run
# can find and remove exactly those rows without touching the small static
# fixture (testteacher1@gmail.com etc.) or reference data.
TEACHER_EMAIL_DOMAIN = "seed.ng"
PARENT_EMAIL_DOMAIN = "seed.ng"
STUDENT_ADMISSION_TAG = "26"

LEVELS = ["JSS 1", "JSS 2", "JSS 3", "SS 1", "SS 2", "SS 3"]
ARMS = ["A", "B", "C", "D", "E", "F"]

CORE_SUBJECTS = [
    ("MTH", "Mathematics"),
    ("ENG", "English Language"),
    ("CIV", "Civic Education"),
]
JUNIOR_ELECTIVES = [
    ("BST", "Basic Science"),
    ("BTE", "Basic Technology"),
    ("SOS", "Social Studies"),
    ("CMP", "Computer Studies"),
    ("BUS", "Business Studies"),
    ("FRE", "French"),
]
SENIOR_ELECTIVES = [
    ("PHY", "Physics"),
    ("CHM", "Chemistry"),
    ("BIO", "Biology"),
    ("ECO", "Economics"),
    ("GOV", "Government"),
    ("LIT", "Literature In English"),
    ("FMT", "Further Mathematics"),
    ("AGR", "Agricultural Science"),
]

fake = Faker()


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


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(DECIMAL_PLACES, rounding=ROUND_HALF_UP)


async def scalar_one_or_none(session, statement: Select):
    result = await session.execute(statement)
    return result.scalar_one_or_none()


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
        raise ValueError("No tenants exist in the database. Create a tenant first.")
    if len(tenants) > 1:
        raise ValueError("Multiple tenants found. Re-run with --tenant-id to avoid seeding the wrong school.")

    return tenants[0]


async def ensure_tenant_ready(session, tenant: Tenant) -> None:
    tenant.verification_status = TenantVerificationStatus.ACTIVE
    if tenant.status not in (TenantStatus.ACTIVE, TenantStatus.TRIAL):
        tenant.status = TenantStatus.TRIAL
    tenant.onboarding_completed = True
    await session.flush()


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

    if not normalized_identifier:
        raise ValueError("Auth identity identifier cannot be empty.")

    identity = AuthIdentity(
        tenant_id=tenant_id,
        identifier=normalized_identifier,
        identifier_type=identifier_type,
        actor_type=actor_type,
        actor_id=actor_id,
        is_active=True,
    )
    session.add(identity)
    return identity


# ---------------------------------------------------------------------------
# Reference / structural data (unchanged upsert pattern — stays small on purpose)
# ---------------------------------------------------------------------------

async def ensure_subject(session, *, tenant_id: uuid.UUID, name: str, code: str, description: str) -> Subject:
    normalized_name = normalize_subject_name(name)
    normalized_code = normalize_subject_code(code)
    if not normalized_name:
        raise ValueError(f"Invalid subject name: {name}")

    subject = await scalar_one_or_none(
        session,
        select(Subject).where(Subject.tenant_id == tenant_id, Subject.normalized_name == normalized_name),
    )
    if subject is None:
        subject = Subject(
            tenant_id=tenant_id, name=name, normalized_name=normalized_name,
            code=normalized_code, normalized_code=normalized_code, description=description, is_active=True,
        )
        session.add(subject)
    else:
        subject.name = name
        subject.code = normalized_code
        subject.normalized_code = normalized_code
        subject.description = description
        subject.is_active = True

    await session.flush()
    return subject


async def ensure_grading_scale(session, *, tenant_id: uuid.UUID, grade: str, min_score: Decimal, max_score: Decimal, remark: str) -> GradingScale:
    normalized_grade = grade.strip().upper()
    scale = await scalar_one_or_none(
        session, select(GradingScale).where(GradingScale.tenant_id == tenant_id, GradingScale.grade == normalized_grade),
    )
    if scale is None:
        scale = GradingScale(tenant_id=tenant_id, grade=normalized_grade, min_score=min_score, max_score=max_score, remark=remark, is_active=True)
        session.add(scale)
    else:
        scale.min_score = min_score
        scale.max_score = max_score
        scale.remark = remark
        scale.is_active = True
    await session.flush()
    return scale


async def ensure_academic_session(session, *, tenant_id: uuid.UUID) -> AcademicSession:
    academic_session = await scalar_one_or_none(
        session, select(AcademicSession).where(AcademicSession.tenant_id == tenant_id, AcademicSession.name == "2025/2026"),
    )
    if academic_session is None:
        academic_session = AcademicSession(
            tenant_id=tenant_id, name="2025/2026", start_date=date(2025, 9, 8), end_date=date(2026, 7, 31),
            is_current=True, is_active=True,
        )
        session.add(academic_session)
    else:
        academic_session.is_current = True
        academic_session.is_active = True

    result = await session.execute(
        select(AcademicSession).where(
            AcademicSession.tenant_id == tenant_id, AcademicSession.name != "2025/2026", AcademicSession.is_current.is_(True),
        )
    )
    for item in result.scalars().all():
        item.is_current = False

    await session.flush()
    return academic_session


async def ensure_academic_term(
    session, *, tenant_id: uuid.UUID, academic_session_id: uuid.UUID, name: AcademicTermName,
    start_date_value: date, end_date_value: date, is_current: bool,
) -> AcademicTerm:
    term = await scalar_one_or_none(
        session,
        select(AcademicTerm).where(
            AcademicTerm.tenant_id == tenant_id, AcademicTerm.academic_session_id == academic_session_id, AcademicTerm.name == name,
        ),
    )
    if term is None:
        term = AcademicTerm(
            tenant_id=tenant_id, academic_session_id=academic_session_id, name=name,
            start_date=start_date_value, end_date=end_date_value, is_current=is_current, is_active=True,
        )
        session.add(term)
    else:
        term.start_date = start_date_value
        term.end_date = end_date_value
        term.is_current = is_current
        term.is_active = True
    await session.flush()
    return term


async def ensure_classroom(session, *, tenant_id: uuid.UUID, payload: ClassSeed, teacher_id: uuid.UUID | None) -> ClassRoom:
    display_name = normalize_class_name(payload.name)
    display_arm = normalize_class_arm(payload.arm)
    normalized_name = normalized_class_name_key(payload.name)
    normalized_arm = normalized_class_arm_key(payload.arm)

    if not display_name or not normalized_name:
        raise ValueError(f"Invalid class name: {payload.name}")

    classroom = await scalar_one_or_none(
        session,
        select(ClassRoom).where(
            ClassRoom.tenant_id == tenant_id, ClassRoom.normalized_name == normalized_name, ClassRoom.normalized_arm == normalized_arm,
        ),
    )
    if classroom is None:
        classroom = ClassRoom(
            tenant_id=tenant_id, name=display_name, arm=display_arm, teacher_id=teacher_id, is_active=True,
        )
        session.add(classroom)
    else:
        classroom.name = display_name
        classroom.arm = display_arm
        classroom.teacher_id = teacher_id
        classroom.is_active = True
    await session.flush()
    return classroom


async def ensure_class_subject(session, *, tenant_id: uuid.UUID, class_id: uuid.UUID, subject_id: uuid.UUID, is_core: bool) -> ClassSubject:
    class_subject = await scalar_one_or_none(
        session, select(ClassSubject).where(ClassSubject.tenant_id == tenant_id, ClassSubject.class_id == class_id, ClassSubject.subject_id == subject_id),
    )
    if class_subject is None:
        class_subject = ClassSubject(tenant_id=tenant_id, class_id=class_id, subject_id=subject_id, is_core=is_core, is_active=True)
        session.add(class_subject)
    else:
        class_subject.is_core = is_core
        class_subject.is_active = True
    await session.flush()
    return class_subject


async def ensure_teacher_assignment(session, *, tenant_id: uuid.UUID, class_subject_id: uuid.UUID, teacher_id: uuid.UUID) -> TeacherAssignment:
    assignment = await scalar_one_or_none(
        session, select(TeacherAssignment).where(TeacherAssignment.class_subject_id == class_subject_id, TeacherAssignment.is_active.is_(True)),
    )
    if assignment is None:
        assignment = TeacherAssignment(
            tenant_id=tenant_id, class_subject_id=class_subject_id, teacher_id=teacher_id, is_active=True,
            effective_from=date(2026, 5, 4), effective_to=None,
        )
        session.add(assignment)
    else:
        assignment.tenant_id = tenant_id
        assignment.teacher_id = teacher_id
        assignment.is_active = True
    await session.flush()
    return assignment


async def ensure_legacy_class_subject_teacher(
    session, *, tenant_id: uuid.UUID, class_id: uuid.UUID, subject_id: uuid.UUID, teacher_id: uuid.UUID, is_core: bool,
) -> ClassSubjectTeacher:
    legacy = await scalar_one_or_none(
        session, select(ClassSubjectTeacher).where(ClassSubjectTeacher.tenant_id == tenant_id, ClassSubjectTeacher.class_id == class_id, ClassSubjectTeacher.subject_id == subject_id),
    )
    if legacy is None:
        legacy = ClassSubjectTeacher(
            tenant_id=tenant_id, class_id=class_id, subject_id=subject_id, teacher_id=teacher_id, is_core=is_core, sort_order=0, is_active=True,
        )
        session.add(legacy)
    else:
        legacy.teacher_id = teacher_id
        legacy.is_core = is_core
        legacy.is_active = True
    await session.flush()
    return legacy


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


# ---------------------------------------------------------------------------
# Bulk Faker generation — direct inserts, batched commits (no per-row upsert)
# ---------------------------------------------------------------------------

async def next_free_index(session, model, field, prefix: str) -> int:
    """Find how many tagged rows already exist so a re-run (without --reset)
    continues numbering instead of colliding on unique constraints."""
    result = await session.execute(select(field).where(field.like(f"{prefix}%")))
    values = list(result.scalars().all())
    return len(values)


def build_teacher_seeds(count: int, start_index: int) -> list[TeacherSeed]:
    all_subjects = CORE_SUBJECTS + JUNIOR_ELECTIVES + SENIOR_ELECTIVES
    seeds = []
    for i in range(start_index, start_index + count):
        _, subject_name = random.choice(all_subjects)
        seeds.append(
            TeacherSeed(
                email=f"{fake.user_name()}.{i}@{TEACHER_EMAIL_DOMAIN}",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                staff_id=f"FK-T-{i:05d}",
                qualification=random.choice(["B.Ed", "B.Sc", "B.A", "M.Ed", "PGDE"]),
                specialization=subject_name,
            )
        )
    return seeds


def build_parent_seeds(count: int, start_index: int) -> list[ParentSeed]:
    seeds = []
    for i in range(start_index, start_index + count):
        seeds.append(
            ParentSeed(
                email=f"{fake.user_name()}.{i}@{PARENT_EMAIL_DOMAIN}",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                phone_number=fake.numerify("080########"),
                occupation=fake.job(),
            )
        )
    return seeds


def build_student_seeds(
    count: int, start_index: int, admission_prefix: str, class_keys: list[str], parent_emails: list[str],
) -> list[StudentSeed]:
    seeds = []
    for i in range(start_index, start_index + count):
        class_key = class_keys[i % len(class_keys)]
        level = class_key.split("-")[0]
        is_junior = level.startswith("jss")
        birth_year_range = (2011, 2014) if is_junior else (2008, 2011)
        seeds.append(
            StudentSeed(
                admission_number=f"{admission_prefix}{STUDENT_ADMISSION_TAG}{i:06d}",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                class_key=class_key,
                gender=random.choice([Gender.MALE, Gender.FEMALE]),
                date_of_birth=fake.date_of_birth(minimum_age=2026 - birth_year_range[1], maximum_age=2026 - birth_year_range[0]),
                parent_email=random.choice(parent_emails),
                relationship_type=random.choice([ParentRelationship.FATHER, ParentRelationship.MOTHER, ParentRelationship.GUARDIAN]),
            )
        )
    return seeds


async def reset_bulk_seed_data(session, *, tenant_id: uuid.UUID, admission_prefix: str) -> None:
    """Delete everything created by a previous run of this bulk seeder.
    Only touches @seed.local teachers/parents and FK-tagged students —
    the static fixture and reference data (subjects, grading scale,
    session/term, classrooms) are left untouched."""

    tagged_student_ids = select(Student.id).where(
        Student.tenant_id == tenant_id,
        Student.admission_number.like(f"{admission_prefix}{STUDENT_ADMISSION_TAG}%"),
    )
    tagged_teacher_ids = select(Teacher.id).where(
        Teacher.tenant_id == tenant_id, Teacher.email.like(f"%@{TEACHER_EMAIL_DOMAIN}"),
    )
    tagged_parent_ids = select(Parent.id).where(
        Parent.tenant_id == tenant_id, Parent.email.like(f"%@{PARENT_EMAIL_DOMAIN}"),
    )

    await session.execute(
        delete(ReportCardSubjectLine).where(
            ReportCardSubjectLine.report_card_id.in_(select(ReportCard.id).where(ReportCard.student_id.in_(tagged_student_ids)))
        )
    )
    await session.execute(delete(ReportCard).where(ReportCard.student_id.in_(tagged_student_ids)))
    await session.execute(delete(StudentSubjectResult).where(StudentSubjectResult.student_id.in_(tagged_student_ids)))
    await session.execute(delete(StudentParentLink).where(StudentParentLink.student_id.in_(tagged_student_ids)))
    await session.execute(delete(TeacherSubject).where(TeacherSubject.teacher_id.in_(tagged_teacher_ids)))
    await session.execute(delete(TeacherAssignment).where(TeacherAssignment.teacher_id.in_(tagged_teacher_ids)))
    await session.execute(delete(ClassSubjectTeacher).where(ClassSubjectTeacher.teacher_id.in_(tagged_teacher_ids)))
    await session.execute(update(ClassRoom).where(ClassRoom.teacher_id.in_(tagged_teacher_ids)).values(teacher_id=None))

    all_tagged_actor_ids = (
        select(Student.id).where(Student.id.in_(tagged_student_ids))
        .union(select(Teacher.id).where(Teacher.id.in_(tagged_teacher_ids)))
        .union(select(Parent.id).where(Parent.id.in_(tagged_parent_ids)))
    )
    await session.execute(delete(AuthIdentity).where(AuthIdentity.actor_id.in_(all_tagged_actor_ids)))

    await session.execute(delete(Student).where(Student.id.in_(tagged_student_ids)))
    await session.execute(delete(Parent).where(Parent.id.in_(tagged_parent_ids)))
    await session.execute(delete(Teacher).where(Teacher.id.in_(tagged_teacher_ids)))

    await session.commit()
    print("Reset complete — previous bulk Faker data removed.")


async def seed_full_dashboard_data(
    *, tenant_id_arg: str | None, draft_results: int, num_students: int, num_teachers: int, num_parents: int,
    reset: bool, faker_seed: int | None,
) -> None:
    if faker_seed is not None:
        Faker.seed(faker_seed)
        random.seed(faker_seed)

    async with AsyncSessionLocal() as session:
        tenant = await resolve_target_tenant(session, tenant_id_arg)
        await ensure_tenant_ready(session, tenant)
        admission_prefix = tenant.admission_number_prefix or "DBS"

        if reset:
            await reset_bulk_seed_data(session, tenant_id=tenant.id, admission_prefix=admission_prefix)

        tenant_admin = await scalar_one_or_none(
            session, select(TenantAdmin).where(TenantAdmin.tenant_id == tenant.id).order_by(TenantAdmin.created_at.asc()),
        )
        if tenant_admin is None:
            raise ValueError("Tenant has no tenant_admin record. Create a tenant admin first.")

        # --- structural: classes ---
        classrooms_by_key: dict[str, ClassRoom] = {}
        class_keys: list[str] = []
        for level in LEVELS:
            level_key = level.lower().replace(" ", "")
            for arm in ARMS:
                key = f"{level_key}-{arm.lower()}"
                classroom = await ensure_classroom(
                    session, tenant_id=tenant.id,
                    payload=ClassSeed(key=key, name=level, arm=arm, homeroom_teacher_email=""),
                    teacher_id=None,  # assigned below once teachers exist
                )
                classrooms_by_key[key] = classroom
                class_keys.append(key)

        # --- structural: subjects ---
        all_subject_defs = CORE_SUBJECTS + JUNIOR_ELECTIVES + SENIOR_ELECTIVES
        subjects_by_code: dict[str, Subject] = {}
        for code, name in all_subject_defs:
            subjects_by_code[code] = await ensure_subject(
                session, tenant_id=tenant.id, name=name, code=code, description=f"{name} curriculum subject",
            )

        # --- structural: grading scale ---
        grading_seed = [
            ("A", Decimal("70"), Decimal("100"), "Excellent"),
            ("B", Decimal("60"), Decimal("69.99"), "Very Good"),
            ("C", Decimal("50"), Decimal("59.99"), "Good"),
            ("D", Decimal("45"), Decimal("49.99"), "Fair"),
            ("E", Decimal("40"), Decimal("44.99"), "Pass"),
            ("F", Decimal("0"), Decimal("39.99"), "Fail"),
        ]
        for grade, min_score, max_score, remark in grading_seed:
            await ensure_grading_scale(session, tenant_id=tenant.id, grade=grade, min_score=min_score, max_score=max_score, remark=remark)

        # --- structural: academic session/term ---
        academic_session = await ensure_academic_session(session, tenant_id=tenant.id)
        await ensure_academic_term(
            session, tenant_id=tenant.id, academic_session_id=academic_session.id, name=AcademicTermName.FIRST_TERM,
            start_date_value=date(2025, 9, 8), end_date_value=date(2025, 12, 19), is_current=False,
        )
        await ensure_academic_term(
            session, tenant_id=tenant.id, academic_session_id=academic_session.id, name=AcademicTermName.SECOND_TERM,
            start_date_value=date(2026, 1, 12), end_date_value=date(2026, 4, 10), is_current=False,
        )
        current_term = await ensure_academic_term(
            session, tenant_id=tenant.id, academic_session_id=academic_session.id, name=AcademicTermName.THIRD_TERM,
            start_date_value=date(2026, 5, 4), end_date_value=date(2026, 7, 31), is_current=True,
        )

        # --- bulk teachers ---
        teacher_start = await next_free_index(session, Teacher, Teacher.staff_id, "FK-T-")
        teacher_seeds = build_teacher_seeds(num_teachers, teacher_start)
        teachers: list[Teacher] = []
        for i, payload in enumerate(teacher_seeds, start=1):
            teacher = Teacher(
                tenant_id=tenant.id, email=payload.email, password_hash=hash_password(DEFAULT_PASSWORD),
                first_name=payload.first_name, last_name=payload.last_name, staff_id=payload.staff_id,
                qualification=payload.qualification, specialization=payload.specialization,
                account_status=TeacherAccountStatus.ACTIVE, status=TeacherStatus.ACTIVE, is_verified=True, is_active=True,
            )
            session.add(teacher)
            teachers.append(teacher)
            if i % 300 == 0:
                await session.flush()
        await session.flush()

        for teacher in teachers:
            await ensure_auth_identity(
                session, tenant_id=tenant.id, identifier=teacher.email, identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.TEACHER, actor_id=teacher.id,
            )
            session.add(TeacherSubject(tenant_id=tenant.id, teacher_id=teacher.id, subject_id=next(
                sub.id for code, name in all_subject_defs for sub in [subjects_by_code[code]] if name == teacher.specialization
            )))
        await session.commit()
        print(f"Bulk teachers created: {len(teachers)}")

        teachers_by_subject: dict[str, list[Teacher]] = defaultdict(list)
        for teacher in teachers:
            teachers_by_subject[teacher.specialization].append(teacher)

        def pick_teacher_for(subject_name: str) -> Teacher:
            pool = teachers_by_subject.get(subject_name) or teachers
            return random.choice(pool)

        # --- assign homeroom teachers + class-subject-teacher links ---
        for level in LEVELS:
            is_junior = level.startswith("JSS")
            elective_pool = JUNIOR_ELECTIVES if is_junior else SENIOR_ELECTIVES
            class_subject_defs = CORE_SUBJECTS + random.sample(elective_pool, k=min(6, len(elective_pool)))
            for arm in ARMS:
                key = f"{level.lower().replace(' ', '')}-{arm.lower()}"
                classroom = classrooms_by_key[key]
                homeroom_teacher = random.choice(teachers)
                classroom.teacher_id = homeroom_teacher.id

                for code, name in class_subject_defs:
                    subject = subjects_by_code[code]
                    subject_teacher = pick_teacher_for(name)
                    class_subject = await ensure_class_subject(
                        session, tenant_id=tenant.id, class_id=classroom.id, subject_id=subject.id, is_core=(code in [c for c, _ in CORE_SUBJECTS]),
                    )
                    await ensure_legacy_class_subject_teacher(
                        session, tenant_id=tenant.id, class_id=classroom.id, subject_id=subject.id, teacher_id=subject_teacher.id, is_core=class_subject.is_core,
                    )
                    await ensure_teacher_assignment(
                        session, tenant_id=tenant.id, class_subject_id=class_subject.id, teacher_id=subject_teacher.id,
                    )
        await session.commit()
        print("Class-subject-teacher assignments ready.")

        # Cache per-class subject list for result generation below
        class_subjects_by_key: dict[str, list[tuple[ClassSubject, ClassSubjectTeacher, TeacherAssignment]]] = {}
        for key, classroom in classrooms_by_key.items():
            result = await session.execute(select(ClassSubject).where(ClassSubject.class_id == classroom.id, ClassSubject.is_active.is_(True)))
            bundle = []
            for class_subject in result.scalars().all():
                legacy = await scalar_one_or_none(
                    session, select(ClassSubjectTeacher).where(ClassSubjectTeacher.class_id == classroom.id, ClassSubjectTeacher.subject_id == class_subject.subject_id),
                )
                assignment = await scalar_one_or_none(
                    session, select(TeacherAssignment).where(TeacherAssignment.class_subject_id == class_subject.id, TeacherAssignment.is_active.is_(True)),
                )
                if legacy and assignment:
                    bundle.append((class_subject, legacy, assignment))
            class_subjects_by_key[key] = bundle

        # --- bulk parents ---
        parent_start = await next_free_index(session, Parent, Parent.email, "")  # rough count via domain filter below
        result = await session.execute(select(Parent.email).where(Parent.email.like(f"%@{PARENT_EMAIL_DOMAIN}")))
        parent_start = len(list(result.scalars().all()))
        parent_seeds = build_parent_seeds(num_parents, parent_start)
        parents: list[Parent] = []
        for i, payload in enumerate(parent_seeds, start=1):
            parent = Parent(
                tenant_id=tenant.id, email=payload.email, password_hash=hash_password(DEFAULT_PASSWORD),
                first_name=payload.first_name, last_name=payload.last_name, phone_number=payload.phone_number,
                occupation=payload.occupation, address=fake.address().replace("\n", ", "),
                emergency_phone=payload.phone_number, account_status=ParentAccountStatus.ACTIVE, is_verified=True, is_active=True,
            )
            session.add(parent)
            parents.append(parent)
            if i % 300 == 0:
                await session.flush()
        await session.flush()
        for parent in parents:
            await ensure_auth_identity(
                session, tenant_id=tenant.id, identifier=parent.email, identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.PARENT, actor_id=parent.id,
            )
        await session.commit()
        print(f"Bulk parents created: {len(parents)}")

        # --- bulk students ---
        result = await session.execute(select(Student.admission_number).where(Student.admission_number.like(f"{admission_prefix}{STUDENT_ADMISSION_TAG}%")))
        student_start = len(list(result.scalars().all()))
        parent_emails = [p.email for p in parents]
        student_seeds = build_student_seeds(num_students, student_start, admission_prefix, class_keys, parent_emails)

        parents_by_email = {p.email: p for p in parents}
        students: list[Student] = []
        for i, payload in enumerate(student_seeds, start=1):
            classroom = classrooms_by_key[payload.class_key]
            student = Student(
                tenant_id=tenant.id, admission_number=payload.admission_number, password_hash=hash_password(DEFAULT_PASSWORD),
                first_name=payload.first_name, last_name=payload.last_name, account_status=StudentAccountStatus.ACTIVE,
                is_verified=True, is_active=True, password_reset_required=False, date_of_birth=payload.date_of_birth,
                gender=payload.gender, class_id=classroom.id, arm=classroom.arm, status=AcademicStatus.ACTIVE,
                profile_status=StudentProfileStatus.COMPLETE, admission_date=date(2025, 9, 8),
            )
            session.add(student)
            students.append(student)
            if i % 300 == 0:
                await session.flush()
        await session.flush()

        for student, payload in zip(students, student_seeds):
            await ensure_auth_identity(
                session, tenant_id=tenant.id, identifier=student.admission_number, identifier_type=IdentifierType.ADMISSION_NUMBER,
                actor_type=ActorType.STUDENT, actor_id=student.id,
            )
            parent = parents_by_email[payload.parent_email]
            session.add(StudentParentLink(
                tenant_id=tenant.id, student_id=student.id, parent_id=parent.id,
                relationship_type=payload.relationship_type, is_primary_contact=True,
                receives_academic_updates=True, receives_fee_updates=True,
            ))
        await session.commit()
        print(f"Bulk students created: {len(students)}")

        # --- bulk results ---
        result_rows: list[StudentSubjectResult] = []
        for i, (student, payload) in enumerate(zip(students, student_seeds), start=1):
            ability_offset = fake.random_int(min=-10, max=15)
            for class_subject, legacy, assignment in class_subjects_by_key[payload.class_key]:
                test_score = max(0, min(20, fake.random_int(min=8, max=20) + ability_offset // 3))
                assessment_score = max(0, min(20, fake.random_int(min=8, max=20) + ability_offset // 3))
                exam_score = max(0, min(60, fake.random_int(min=20, max=60) + ability_offset))
                total_score = money(Decimal(test_score) + Decimal(assessment_score) + Decimal(exam_score))
                grade, remark = resolve_grade(total_score)

                row = StudentSubjectResult(
                    tenant_id=tenant.id, student_id=student.id, class_id=class_subject.class_id, subject_id=class_subject.subject_id,
                    teacher_id=assignment.teacher_id, class_subject_teacher_id=legacy.id, teacher_assignment_id=assignment.id,
                    academic_session_id=academic_session.id, academic_term_id=current_term.id,
                    recorded_by_actor_type=ActorType.TENANT_ADMIN.value, recorded_by_actor_id=tenant_admin.id,
                    test_score=money(test_score), assessment_score=money(assessment_score), exam_score=money(exam_score),
                    total_score=total_score, grade=grade, remark=remark, status=AcademicResultStatus.SUBMITTED,
                )
                session.add(row)
                result_rows.append(row)

            if i % 200 == 0:
                await session.commit()
                print(f"  ...results generated for {i}/{len(students)} students")
        await session.commit()
        print(f"Bulk result rows created: {len(result_rows)}")

        draft_count = await ensure_some_draft_results(session, tenant_id=tenant.id, max_drafts=max(draft_results, 0))
        await session.commit()

        # --- report cards (ranked within class) ---
        result = await session.execute(
            select(StudentSubjectResult).where(
                StudentSubjectResult.tenant_id == tenant.id,
                StudentSubjectResult.academic_session_id == academic_session.id,
                StudentSubjectResult.academic_term_id == current_term.id,
            )
        )
        all_results = list(result.scalars().all())
        results_by_student: dict[uuid.UUID, list[StudentSubjectResult]] = defaultdict(list)
        for row in all_results:
            results_by_student[row.student_id].append(row)

        student_averages: list[tuple[Student, Decimal]] = []
        for student_id, rows in results_by_student.items():
            student = await session.get(Student, student_id)
            if student is None:
                continue
            submitted_rows = [row for row in rows if row.status == AcademicResultStatus.SUBMITTED]
            if not submitted_rows:
                continue
            average = money(sum((Decimal(row.total_score or 0) for row in submitted_rows), Decimal("0")) / Decimal(len(submitted_rows)))
            student_averages.append((student, average))

        students_by_class: dict[uuid.UUID, list[tuple[Student, Decimal]]] = defaultdict(list)
        for student, average in student_averages:
            students_by_class[student.class_id].append((student, average))

        position_map: dict[uuid.UUID, tuple[int, int]] = {}
        for _class_id, rows in students_by_class.items():
            ranked_rows = sorted(rows, key=lambda item: item[1], reverse=True)
            out_of = len(ranked_rows)
            for position, (student, _average) in enumerate(ranked_rows, start=1):
                position_map[student.id] = (position, out_of)

        generated_report_cards = 0
        published_report_cards = 0
        for index, (student, _average) in enumerate(student_averages, start=1):
            position, out_of = position_map[student.id]
            should_publish = index % 4 != 0
            report_card = await ensure_report_card(
                session, tenant_id=tenant.id, student=student, results=results_by_student[student.id],
                academic_session=academic_session, academic_term=current_term, tenant_admin=tenant_admin,
                position=position, position_out_of=out_of, should_publish=should_publish,
            )
            if report_card is not None:
                generated_report_cards += 1
                if report_card.status == ReportCardStatus.PUBLISHED:
                    published_report_cards += 1
            if index % 200 == 0:
                await session.commit()
                print(f"  ...report cards generated for {index}/{len(student_averages)} students")

        await session.commit()

    print("Bulk Faker seeding complete.")
    print(f"Tenant: {tenant.school_name} ({tenant.id})")
    print(f"Bulk teachers: {len(teachers)} | Bulk parents: {len(parents)} | Bulk students: {len(students)}")
    print(f"Result rows: {len(result_rows)} | Draft rows left pending: {draft_count}")
    print(f"Report cards generated: {generated_report_cards} | Published: {published_report_cards}")
    print(f"Sample bulk student login: {student_seeds[0].admission_number} / {DEFAULT_PASSWORD}")
    print(f"Sample bulk teacher login: {teacher_seeds[0].email} / {DEFAULT_PASSWORD}")
    print(f"Sample bulk parent login: {parent_seeds[0].email} / {DEFAULT_PASSWORD}")


async def ensure_some_draft_results(session, *, tenant_id: uuid.UUID, max_drafts: int) -> int:
    if max_drafts <= 0:
        return 0
    result = await session.execute(
        select(StudentSubjectResult).where(StudentSubjectResult.tenant_id == tenant_id)
        .order_by(StudentSubjectResult.created_at.desc()).limit(max_drafts)
    )
    rows = list(result.scalars().all())
    for row in rows:
        row.status = AcademicResultStatus.DRAFT
    await session.flush()
    return len(rows)


async def ensure_report_card(
    session, *, tenant_id: uuid.UUID, student: Student, results: list[StudentSubjectResult],
    academic_session: AcademicSession, academic_term: AcademicTerm, tenant_admin: TenantAdmin,
    position: int, position_out_of: int, should_publish: bool,
) -> ReportCard | None:
    submitted_results = [row for row in results if row.status == AcademicResultStatus.SUBMITTED]
    if not submitted_results:
        return None

    total_score = money(sum((Decimal(row.total_score or 0) for row in submitted_results), Decimal("0")))
    average_score = money(total_score / Decimal(len(submitted_results)))
    status = ReportCardStatus.PUBLISHED if should_publish else ReportCardStatus.DRAFT

    report_card = ReportCard(
        tenant_id=tenant_id, student_id=student.id, class_id=student.class_id,
        academic_session_id=academic_session.id, academic_term_id=academic_term.id,
        total_score=total_score, average_score=average_score, position=position, position_out_of=position_out_of,
        class_teacher_comment="Good performance. Keep improving consistency across all subjects.",
        principal_comment="Strong effort recorded. Maintain steady academic focus.",
        generated_by_actor_type=ActorType.TENANT_ADMIN.value, generated_by_actor_id=tenant_admin.id,
        status=status, published_at=datetime.now(UTC) if should_publish else None,
        published_by=tenant_admin.id if should_publish else None,
    )
    session.add(report_card)
    await session.flush()

    for row in submitted_results:
        subject = await session.get(Subject, row.subject_id)
        teacher = await session.get(Teacher, row.teacher_id)
        teacher_name = None
        if teacher is not None:
            teacher_name = " ".join([teacher.first_name or "", teacher.last_name or ""]).strip() or teacher.email

        session.add(ReportCardSubjectLine(
            tenant_id=tenant_id, report_card_id=report_card.id, student_subject_result_id=row.id,
            subject_id=row.subject_id, subject_name=subject.name if subject else "Subject",
            subject_code=subject.code if subject else None, teacher_name=teacher_name,
            test_score=money(row.test_score or 0), assessment_score=money(row.assessment_score or 0),
            exam_score=money(row.exam_score or 0), total_score=money(row.total_score or 0),
            grade=row.grade or "--", remark=row.remark,
        ))

    await session.flush()
    return report_card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk-seed a tenant with Faker-generated demo data for load/UI testing.")
    parser.add_argument("--tenant-id", help="Explicit tenant ID. Required when more than one tenant exists.")
    parser.add_argument("--students", type=int, default=1000, help="Number of bulk students to generate.")
    parser.add_argument("--teachers", type=int, default=120, help="Number of bulk teachers to generate.")
    parser.add_argument("--parents", type=int, default=700, help="Number of bulk parents to generate.")
    parser.add_argument("--draft-results", type=int, default=150, help="Number of result rows to leave as draft.")
    parser.add_argument("--reset", action="store_true", help="Delete previously bulk-generated data before reseeding.")
    parser.add_argument("--seed", type=int, default=None, help="Faker/random seed for reproducible output.")
    parser.add_argument("--no-login-check", action="store_true", help="Skip login verification after seeding.")
    return parser.parse_args()


async def verify_demo_logins(tenant_id_arg: str | None) -> None:
    async with AsyncSessionLocal() as session:
        tenant = await resolve_target_tenant(session, tenant_id_arg)
        result = await session.execute(select(Teacher.email).where(Teacher.email.like(f"%@{TEACHER_EMAIL_DOMAIN}")).limit(1))
        sample_teacher_email = result.scalar_one_or_none()
        result = await session.execute(select(Student.admission_number).where(
            Student.admission_number.like(f"{tenant.admission_number_prefix or 'DBS'}{STUDENT_ADMISSION_TAG}%")
        ).limit(1))
        sample_admission_number = result.scalar_one_or_none()

        if sample_teacher_email:
            auth = await AuthService.authenticate_actor(session, LoginRequest(identifier=sample_teacher_email, password=DEFAULT_PASSWORD))
            print(f"Verified bulk teacher login: {auth.actor_type}")
        if sample_admission_number:
            auth = await AuthService.authenticate_actor(session, LoginRequest(identifier=sample_admission_number, password=DEFAULT_PASSWORD))
            print(f"Verified bulk student login: {auth.actor_type}")


async def main() -> None:
    args = parse_args()
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    await seed_full_dashboard_data(
        tenant_id_arg=args.tenant_id, draft_results=args.draft_results,
        num_students=args.students, num_teachers=args.teachers, num_parents=args.parents,
        reset=args.reset, faker_seed=args.seed,
    )

    if not args.no_login_check:
        await verify_demo_logins(args.tenant_id)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
