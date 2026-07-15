from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Select, delete, select

# Expected location: backend/scripts/weave_full_school_seed_with_scores.py
# If you place it somewhere else, adjust BACKEND_DIR accordingly.
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
BULK_TAG = "bulkload"
ACADEMIC_SESSION_NAME = "2025/2026"
ADMISSION_YEAR_DIGITS = "26"
RANDOM_SEED = 42

# Result policy: total = 20 + 20 + 60 = 100
MAX_TEST_SCORE = Decimal("20")
MAX_ASSESSMENT_SCORE = Decimal("20")
MAX_EXAM_SCORE = Decimal("60")

LEVELS = [
    ("JSS 1", "Junior Secondary 1"),
    ("JSS 2", "Junior Secondary 2"),
    ("JSS 3", "Junior Secondary 3"),
    ("SS 1", "Senior Secondary 1"),
    ("SS 2", "Senior Secondary 2"),
    ("SS 3", "Senior Secondary 3"),
]
DEFAULT_ARMS = ["A", "B", "C", "D"]

# JSS students take junior subjects. SS arms are treated as simple tracks:
# A = science, B = commercial, C = arts/humanities, D = mixed/general.
SUBJECTS = [
    ("MTH", "Mathematics", "Core mathematics"),
    ("ENG", "English Language", "Reading, grammar, and writing"),
    ("BST", "Basic Science", "Integrated junior science"),
    ("BTE", "Basic Technology", "Introductory technology"),
    ("CMP", "Computer Studies", "Digital literacy and computing"),
    ("SOS", "Social Studies", "Society and civic awareness"),
    ("CIV", "Civic Education", "Citizenship and values"),
    ("BUS", "Business Studies", "Introductory business studies"),
    ("PHY", "Physics", "Senior secondary physics"),
    ("CHE", "Chemistry", "Senior secondary chemistry"),
    ("BIO", "Biology", "Senior secondary biology"),
    ("ECO", "Economics", "Senior secondary economics"),
    ("ACC", "Financial Accounting", "Commerce and accounting"),
    ("GOV", "Government", "Government and civic institutions"),
    ("LIT", "Literature in English", "Literary studies"),
    ("CRS", "Christian Religious Studies", "Religious and moral studies"),
]

JSS_SUBJECT_CODES = ["MTH", "ENG", "BST", "BTE", "CMP", "SOS", "CIV", "BUS"]
SS_SCIENCE_CODES = ["MTH", "ENG", "CMP", "CIV", "PHY", "CHE", "BIO", "ECO"]
SS_COMMERCIAL_CODES = ["MTH", "ENG", "CMP", "CIV", "ECO", "ACC", "GOV", "BUS"]
SS_ARTS_CODES = ["MTH", "ENG", "CMP", "CIV", "GOV", "LIT", "CRS", "ECO"]
SS_MIXED_CODES = ["MTH", "ENG", "CMP", "CIV", "BIO", "ECO", "GOV", "LIT"]

FIRST_NAMES_MALE = [
    "Emeka", "Tunde", "Yusuf", "Chidi", "Femi", "Uche", "Segun", "Obinna",
    "Ayodele", "Kelechi", "Musa", "Chibuike", "Wale", "Nnamdi", "Bashir",
    "Tobi", "Ikenna", "Rasheed", "Chukwuma", "Damilare",
]
FIRST_NAMES_FEMALE = [
    "Amaka", "Bisi", "Fatima", "Ijeoma", "Kemi", "Ngozi", "Zainab", "Adaeze",
    "Funke", "Halima", "Chiamaka", "Yetunde", "Blessing", "Aminat", "Ebele",
    "Folake", "Hauwa", "Chinwe", "Omolara", "Nkechi",
]
LAST_NAMES = [
    "Okafor", "Adewale", "Bello", "Ike", "Yusuf", "Eze", "Balogun", "Nwosu",
    "Abubakar", "Onyekachi", "Fashola", "Chukwu", "Suleiman", "Okonkwo",
    "Adeyemi", "Mohammed", "Nnaji", "Obi", "Lawal", "Ibrahim", "Umeh",
    "Sani", "Anyanwu", "Oduya", "Garba", "Njoku", "Adebayo", "Musa",
    "Chibundu", "Yakubu",
]
OCCUPATIONS = [
    "Trader", "Nurse", "Engineer", "Civil Servant", "Teacher", "Driver",
    "Accountant", "Tailor", "Farmer", "Electrician", "Banker", "Caterer",
]
QUALIFICATIONS = ["B.Ed", "B.Sc", "B.A", "B.Tech", "M.Ed", "PGDE"]


@dataclass(frozen=True)
class TeacherSeed:
    email: str
    first_name: str
    last_name: str
    staff_id: str
    qualification: str
    specialization_code: str


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
    offered_subject_codes: list[str]


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


def bulk_teacher_email(index: int) -> str:
    return f"{BULK_TAG}teacher{index:04d}@gmail.com"


def bulk_parent_email(index: int) -> str:
    return f"{BULK_TAG}parent{index:04d}@gmail.com"


def bulk_admission_number(prefix: str, index: int) -> str:
    # Example: DBS26000001. This avoids relying on prefix length during purge/tests.
    return f"{prefix}{ADMISSION_YEAR_DIGITS}{index:06d}"


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


async def get_tenant_admin(session, tenant_id: uuid.UUID) -> TenantAdmin:
    tenant_admin = await scalar_one_or_none(
        session,
        select(TenantAdmin)
        .where(TenantAdmin.tenant_id == tenant_id)
        .order_by(TenantAdmin.created_at.asc()),
    )
    if tenant_admin is None:
        raise ValueError("Tenant has no tenant_admin record; cannot attribute result/audit rows safely.")
    return tenant_admin


def subject_codes_for_class(level_name: str, arm: str) -> list[str]:
    if level_name.startswith("JSS"):
        return JSS_SUBJECT_CODES.copy()
    if arm == "A":
        return SS_SCIENCE_CODES.copy()
    if arm == "B":
        return SS_COMMERCIAL_CODES.copy()
    if arm == "C":
        return SS_ARTS_CODES.copy()
    return SS_MIXED_CODES.copy()


def generate_teachers(count: int) -> list[TeacherSeed]:
    subject_codes = [code for code, _, _ in SUBJECTS]
    teachers: list[TeacherSeed] = []
    for i in range(1, count + 1):
        is_male = i % 2 == 0
        first = FIRST_NAMES_MALE[i % len(FIRST_NAMES_MALE)] if is_male else FIRST_NAMES_FEMALE[i % len(FIRST_NAMES_FEMALE)]
        last = LAST_NAMES[(i * 3) % len(LAST_NAMES)]
        specialization_code = subject_codes[(i - 1) % len(subject_codes)]
        teachers.append(
            TeacherSeed(
                email=bulk_teacher_email(i),
                first_name=first,
                last_name=last,
                staff_id=f"BLK-TCH-{i:04d}",
                qualification=QUALIFICATIONS[i % len(QUALIFICATIONS)],
                specialization_code=specialization_code,
            )
        )
    return teachers


def generate_parents(count: int) -> list[ParentSeed]:
    parents: list[ParentSeed] = []
    for i in range(1, count + 1):
        is_male = i % 2 == 0
        first = FIRST_NAMES_MALE[(i * 5) % len(FIRST_NAMES_MALE)] if is_male else FIRST_NAMES_FEMALE[(i * 5) % len(FIRST_NAMES_FEMALE)]
        last = LAST_NAMES[i % len(LAST_NAMES)]
        parents.append(
            ParentSeed(
                email=bulk_parent_email(i),
                first_name=first,
                last_name=last,
                phone_number=f"0803{i:07d}",
                occupation=OCCUPATIONS[i % len(OCCUPATIONS)],
            )
        )
    return parents


def generate_classes(teachers: list[TeacherSeed], arms: list[str]) -> list[ClassSeed]:
    classes: list[ClassSeed] = []
    for class_index, (name, level) in enumerate(LEVELS):
        for arm_index, arm in enumerate(arms):
            key = f"bulk-{name.replace(' ', '').lower()}-{arm.lower()}"
            teacher = teachers[(class_index * len(arms) + arm_index) % len(teachers)]
            classes.append(
                ClassSeed(
                    key=key,
                    name=f"Bulk {name}",
                    arm=arm,
                    homeroom_teacher_email=teacher.email,
                    offered_subject_codes=subject_codes_for_class(name, arm),
                )
            )
    return classes


def generate_students(
    *,
    count: int,
    admission_prefix: str,
    classes: list[ClassSeed],
    parents: list[ParentSeed],
) -> list[StudentSeed]:
    students: list[StudentSeed] = []
    relationships = [ParentRelationship.FATHER, ParentRelationship.MOTHER, ParentRelationship.GUARDIAN]
    for i in range(1, count + 1):
        is_male = i % 2 == 0
        first = FIRST_NAMES_MALE[(i * 7) % len(FIRST_NAMES_MALE)] if is_male else FIRST_NAMES_FEMALE[(i * 7) % len(FIRST_NAMES_FEMALE)]
        parent = parents[((i - 1) // 2) % len(parents)]
        classroom = classes[(i - 1) % len(classes)]
        birth_year = 2010 + (i % 7)
        students.append(
            StudentSeed(
                admission_number=bulk_admission_number(admission_prefix, i),
                first_name=first,
                last_name=parent.last_name,
                class_key=classroom.key,
                gender=Gender.MALE if is_male else Gender.FEMALE,
                date_of_birth=date(birth_year, 1 + (i % 12), 1 + (i % 27)),
                parent_email=parent.email,
                relationship_type=relationships[i % len(relationships)],
            )
        )
    return students


def resolve_score_components(student_index: int, subject_index: int, term_index: int) -> tuple[Decimal, Decimal, Decimal]:
    # Deterministic but varied. Keeps totals realistic and always within 100.
    test_score = Decimal(str(8 + ((student_index + subject_index + term_index) % 13)))
    assessment_score = Decimal(str(9 + ((student_index * 2 + subject_index + term_index) % 12)))
    exam_score = Decimal(str(28 + ((student_index * 3 + subject_index * 2 + term_index) % 33)))

    test_score = min(test_score, MAX_TEST_SCORE)
    assessment_score = min(assessment_score, MAX_ASSESSMENT_SCORE)
    exam_score = min(exam_score, MAX_EXAM_SCORE)
    return test_score, assessment_score, exam_score


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
    else:
        identity.tenant_id = tenant_id
        identity.actor_type = actor_type
        identity.actor_id = actor_id
        identity.is_active = True
    await session.flush()
    return identity


async def ensure_subjects(session, tenant_id: uuid.UUID) -> dict[str, Subject]:
    subjects_by_code: dict[str, Subject] = {}
    for code, name, description in SUBJECTS:
        normalized_code = normalize_subject_code(code)
        normalized_name = normalize_subject_name(name)
        subject = await scalar_one_or_none(
            session,
            select(Subject).where(
                Subject.tenant_id == tenant_id,
                Subject.normalized_code == normalized_code,
            ),
        )
        if subject is None:
            subject = Subject(
                tenant_id=tenant_id,
                name=name,
                normalized_name=normalized_name,
                code=normalized_code,
                normalized_code=normalized_code,
                description=description,
                is_active=True,
            )
            session.add(subject)
        else:
            subject.name = name
            subject.normalized_name = normalized_name
            subject.code = normalized_code
            subject.normalized_code = normalized_code
            subject.description = description
            subject.is_active = True
        await session.flush()
        subjects_by_code[normalized_code] = subject
    return subjects_by_code


async def ensure_academic_calendar(session, tenant_id: uuid.UUID) -> tuple[AcademicSession, list[AcademicTerm]]:
    academic_session = await scalar_one_or_none(
        session,
        select(AcademicSession).where(
            AcademicSession.tenant_id == tenant_id,
            AcademicSession.name == ACADEMIC_SESSION_NAME,
        ),
    )
    if academic_session is None:
        academic_session = AcademicSession(
            tenant_id=tenant_id,
            name=ACADEMIC_SESSION_NAME,
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
    await session.flush()

    term_payloads = [
        (AcademicTermName.FIRST_TERM, date(2025, 9, 8), date(2025, 12, 19), False),
        (AcademicTermName.SECOND_TERM, date(2026, 1, 12), date(2026, 4, 10), False),
        (AcademicTermName.THIRD_TERM, date(2026, 5, 4), date(2026, 7, 31), True),
    ]
    terms: list[AcademicTerm] = []
    for name, start, end, is_current in term_payloads:
        term = await scalar_one_or_none(
            session,
            select(AcademicTerm).where(
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.academic_session_id == academic_session.id,
                AcademicTerm.name == name,
            ),
        )
        if term is None:
            term = AcademicTerm(
                tenant_id=tenant_id,
                academic_session_id=academic_session.id,
                name=name,
                start_date=start,
                end_date=end,
                is_current=is_current,
                is_active=True,
            )
            session.add(term)
        else:
            term.start_date = start
            term.end_date = end
            term.is_current = is_current
            term.is_active = True
        await session.flush()
        terms.append(term)
    return academic_session, terms


async def ensure_grading_scale(session, tenant_id: uuid.UUID) -> None:
    grading_seed = [
        ("A", Decimal("70"), Decimal("100"), "Excellent"),
        ("B", Decimal("60"), Decimal("69.99"), "Very Good"),
        ("C", Decimal("50"), Decimal("59.99"), "Good"),
        ("D", Decimal("45"), Decimal("49.99"), "Fair"),
        ("E", Decimal("40"), Decimal("44.99"), "Pass"),
        ("F", Decimal("0"), Decimal("39.99"), "Fail"),
    ]
    for grade, min_score, max_score, remark in grading_seed:
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


async def has_bulk_seed(session, tenant_id: uuid.UUID) -> bool:
    marker = await scalar_one_or_none(
        session,
        select(Teacher.id).where(
            Teacher.tenant_id == tenant_id,
            Teacher.email == bulk_teacher_email(1),
        ),
    )
    return marker is not None


async def purge_bulk_school(session, tenant_id: uuid.UUID, admission_prefix: str) -> None:
    print("Purging generated bulk school data...")
    admission_like = f"{admission_prefix}{ADMISSION_YEAR_DIGITS}%"

    student_result = await session.execute(
        select(Student.id).where(
            Student.tenant_id == tenant_id,
            Student.admission_number.like(admission_like),
        )
    )
    student_ids = [row[0] for row in student_result.all()]

    class_result = await session.execute(
        select(ClassRoom.id).where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.name.like("Bulk %"),
        )
    )
    class_ids = [row[0] for row in class_result.all()]

    parent_result = await session.execute(
        select(Parent.id).where(
            Parent.tenant_id == tenant_id,
            Parent.email.like(f"{BULK_TAG}parent%"),
        )
    )
    parent_ids = [row[0] for row in parent_result.all()]

    teacher_result = await session.execute(
        select(Teacher.id).where(
            Teacher.tenant_id == tenant_id,
            Teacher.email.like(f"{BULK_TAG}teacher%"),
        )
    )
    teacher_ids = [row[0] for row in teacher_result.all()]

    if student_ids:
        await session.execute(delete(StudentSubjectResult).where(StudentSubjectResult.student_id.in_(student_ids)))
        await session.execute(delete(StudentParentLink).where(StudentParentLink.student_id.in_(student_ids)))
        await session.execute(delete(AuthIdentity).where(
            AuthIdentity.actor_type == ActorType.STUDENT,
            AuthIdentity.actor_id.in_(student_ids),
        ))
        await session.execute(delete(Student).where(Student.id.in_(student_ids)))

    if class_ids:
        class_subject_ids_result = await session.execute(
            select(ClassSubject.id).where(ClassSubject.class_id.in_(class_ids))
        )
        class_subject_ids = [row[0] for row in class_subject_ids_result.all()]
        if class_subject_ids:
            await session.execute(delete(TeacherAssignment).where(TeacherAssignment.class_subject_id.in_(class_subject_ids)))
            await session.execute(delete(ClassSubject).where(ClassSubject.id.in_(class_subject_ids)))
        await session.execute(delete(ClassSubjectTeacher).where(ClassSubjectTeacher.class_id.in_(class_ids)))
        await session.execute(delete(ClassRoom).where(ClassRoom.id.in_(class_ids)))

    if parent_ids:
        await session.execute(delete(AuthIdentity).where(
            AuthIdentity.actor_type == ActorType.PARENT,
            AuthIdentity.actor_id.in_(parent_ids),
        ))
        await session.execute(delete(Parent).where(Parent.id.in_(parent_ids)))

    if teacher_ids:
        await session.execute(delete(TeacherSubject).where(TeacherSubject.teacher_id.in_(teacher_ids)))
        await session.execute(delete(AuthIdentity).where(
            AuthIdentity.actor_type == ActorType.TEACHER,
            AuthIdentity.actor_id.in_(teacher_ids),
        ))
        await session.execute(delete(Teacher).where(Teacher.id.in_(teacher_ids)))

    await session.commit()
    print(
        "Purged:",
        f"students={len(student_ids)}",
        f"classes={len(class_ids)}",
        f"parents={len(parent_ids)}",
        f"teachers={len(teacher_ids)}",
    )


async def seed_full_school(
    *,
    tenant_id_arg: str | None,
    student_count: int,
    teacher_count: int | None,
    parent_count: int | None,
    arms: list[str],
    reset: bool,
) -> None:
    started_at = time.monotonic()
    random.seed(RANDOM_SEED)
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    async with AsyncSessionLocal() as session:
        tenant = await resolve_target_tenant(session, tenant_id_arg)
        await ensure_tenant_ready(session, tenant)
        tenant_admin = await get_tenant_admin(session, tenant.id)
        admission_prefix = tenant.admission_number_prefix or "DBS"

        if reset:
            await purge_bulk_school(session, tenant.id, admission_prefix)

        if await has_bulk_seed(session, tenant.id):
            print("Bulk school data already exists for this tenant. Re-run with --reset to regenerate it.")
            return

        subjects_by_code = await ensure_subjects(session, tenant.id)
        academic_session, terms = await ensure_academic_calendar(session, tenant.id)
        await ensure_grading_scale(session, tenant.id)
        await session.commit()

        teacher_count = teacher_count or max(len(SUBJECTS) * 2, student_count // 20, 24)
        parent_count = parent_count or max(50, student_count // 2)

        teacher_seeds = generate_teachers(teacher_count)
        parent_seeds = generate_parents(parent_count)
        class_seeds = generate_classes(teacher_seeds, arms)
        student_seeds = generate_students(
            count=student_count,
            admission_prefix=admission_prefix,
            classes=class_seeds,
            parents=parent_seeds,
        )

        shared_password_hash = hash_password(DEFAULT_PASSWORD)

        # Teachers
        teachers_by_email: dict[str, Teacher] = {}
        teacher_batch: list[Teacher] = []
        for payload in teacher_seeds:
            subject_name = subjects_by_code[payload.specialization_code].name
            teacher = Teacher(
                tenant_id=tenant.id,
                email=payload.email,
                password_hash=shared_password_hash,
                first_name=payload.first_name,
                last_name=payload.last_name,
                staff_id=payload.staff_id,
                qualification=payload.qualification,
                specialization=subject_name,
                account_status=TeacherAccountStatus.ACTIVE,
                status=TeacherStatus.ACTIVE,
                is_verified=True,
                is_active=True,
            )
            session.add(teacher)
            teacher_batch.append(teacher)
        await session.flush()

        for teacher, payload in zip(teacher_batch, teacher_seeds, strict=True):
            teachers_by_email[teacher.email] = teacher
            session.add(AuthIdentity(
                tenant_id=tenant.id,
                identifier=teacher.email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.TEACHER,
                actor_id=teacher.id,
                is_active=True,
            ))
            session.add(TeacherSubject(
                tenant_id=tenant.id,
                teacher_id=teacher.id,
                subject_id=subjects_by_code[payload.specialization_code].id,
            ))
        await session.flush()
        print(f"[{time.monotonic() - started_at:.1f}s] Created teachers: {len(teacher_batch)}")

        # Parents
        parents_by_email: dict[str, Parent] = {}
        parent_batch: list[Parent] = []
        for payload in parent_seeds:
            parent = Parent(
                tenant_id=tenant.id,
                email=payload.email,
                password_hash=shared_password_hash,
                first_name=payload.first_name,
                last_name=payload.last_name,
                phone_number=payload.phone_number,
                occupation=payload.occupation,
                address="Bulk Test Address, Lagos",
                emergency_phone=payload.phone_number,
                account_status=ParentAccountStatus.ACTIVE,
                is_verified=True,
                is_active=True,
            )
            session.add(parent)
            parent_batch.append(parent)
        await session.flush()

        for parent in parent_batch:
            parents_by_email[parent.email] = parent
            session.add(AuthIdentity(
                tenant_id=tenant.id,
                identifier=parent.email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.PARENT,
                actor_id=parent.id,
                is_active=True,
            ))
        await session.flush()
        print(f"[{time.monotonic() - started_at:.1f}s] Created parents: {len(parent_batch)}")

        # Classes
        classrooms_by_key: dict[str, ClassRoom] = {}
        class_batch: list[tuple[ClassSeed, ClassRoom]] = []
        for payload in class_seeds:
            homeroom_teacher = teachers_by_email[payload.homeroom_teacher_email]
            classroom = ClassRoom(
                tenant_id=tenant.id,
                name=payload.name,
                arm=payload.arm,
                teacher_id=homeroom_teacher.id,
                is_active=True,
            )
            session.add(classroom)
            class_batch.append((payload, classroom))
        await session.flush()

        for payload, classroom in class_batch:
            classrooms_by_key[payload.key] = classroom
        print(f"[{time.monotonic() - started_at:.1f}s] Created classes: {len(class_batch)}")

        # Class subjects + legacy class-subject-teacher + new assignment
        assignment_bundle_by_class_subject: dict[tuple[uuid.UUID, str], tuple[Subject, ClassSubject, ClassSubjectTeacher, TeacherAssignment]] = {}
        subject_teacher_cursor: dict[str, int] = {code: 0 for code, _, _ in SUBJECTS}
        teachers_by_subject_code: dict[str, list[Teacher]] = {code: [] for code, _, _ in SUBJECTS}
        for teacher, payload in zip(teacher_batch, teacher_seeds, strict=True):
            teachers_by_subject_code[payload.specialization_code].append(teacher)

        for class_payload, classroom in class_batch:
            for sort_order, subject_code in enumerate(class_payload.offered_subject_codes):
                subject = subjects_by_code[subject_code]
                qualified_teachers = teachers_by_subject_code[subject_code] or teacher_batch
                teacher_cursor = subject_teacher_cursor[subject_code]
                teacher = qualified_teachers[teacher_cursor % len(qualified_teachers)]
                subject_teacher_cursor[subject_code] = teacher_cursor + 1

                class_subject = ClassSubject(
                    tenant_id=tenant.id,
                    class_id=classroom.id,
                    subject_id=subject.id,
                    is_core=True,
                    is_active=True,
                )
                session.add(class_subject)
                legacy_assignment = ClassSubjectTeacher(
                    tenant_id=tenant.id,
                    class_id=classroom.id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                    is_core=True,
                    sort_order=sort_order,
                    is_active=True,
                )
                session.add(legacy_assignment)
                await session.flush()

                teacher_assignment = TeacherAssignment(
                    tenant_id=tenant.id,
                    class_subject_id=class_subject.id,
                    teacher_id=teacher.id,
                    is_active=True,
                    effective_from=date(2025, 9, 8),
                    effective_to=None,
                )
                session.add(teacher_assignment)
                await session.flush()

                assignment_bundle_by_class_subject[(classroom.id, subject_code)] = (
                    subject,
                    class_subject,
                    legacy_assignment,
                    teacher_assignment,
                )
        print(f"[{time.monotonic() - started_at:.1f}s] Linked class subjects and teacher assignments")

        # Students + student identities
        FLUSH_EVERY = 250
        students_created: list[tuple[int, Student, StudentSeed]] = []
        pending_students: list[Student] = []
        for index, payload in enumerate(student_seeds, start=1):
            classroom = classrooms_by_key[payload.class_key]
            student = Student(
                tenant_id=tenant.id,
                admission_number=payload.admission_number,
                password_hash=shared_password_hash,
                first_name=payload.first_name,
                last_name=payload.last_name,
                account_status=StudentAccountStatus.ACTIVE,
                is_verified=True,
                is_active=True,
                password_reset_required=False,
                date_of_birth=payload.date_of_birth,
                gender=payload.gender,
                class_id=classroom.id,
                arm=classroom.arm,
                status=AcademicStatus.ACTIVE,
                profile_status=StudentProfileStatus.COMPLETE,
                admission_date=date(2025, 9, 8),
            )
            session.add(student)
            pending_students.append(student)
            students_created.append((index, student, payload))

            if len(pending_students) >= FLUSH_EVERY:
                await session.flush()
                for pending_student in pending_students:
                    session.add(AuthIdentity(
                        tenant_id=tenant.id,
                        identifier=pending_student.admission_number,
                        identifier_type=IdentifierType.ADMISSION_NUMBER,
                        actor_type=ActorType.STUDENT,
                        actor_id=pending_student.id,
                        is_active=True,
                    ))
                await session.flush()
                pending_students = []
                print(f"[{time.monotonic() - started_at:.1f}s] Created students: {index}/{student_count}")

        if pending_students:
            await session.flush()
            for pending_student in pending_students:
                session.add(AuthIdentity(
                    tenant_id=tenant.id,
                    identifier=pending_student.admission_number,
                    identifier_type=IdentifierType.ADMISSION_NUMBER,
                    actor_type=ActorType.STUDENT,
                    actor_id=pending_student.id,
                    is_active=True,
                ))
            await session.flush()
        print(f"[{time.monotonic() - started_at:.1f}s] Created students: {len(students_created)}")

        # Parent links
        for _index, student, payload in students_created:
            parent = parents_by_email[payload.parent_email]
            session.add(StudentParentLink(
                tenant_id=tenant.id,
                student_id=student.id,
                parent_id=parent.id,
                relationship_type=payload.relationship_type,
                is_primary_contact=True,
                receives_academic_updates=True,
                receives_fee_updates=True,
            ))
        await session.flush()
        print(f"[{time.monotonic() - started_at:.1f}s] Linked students to parents")

        # Results: test + assessment + exam for every student's offered subjects across all 3 terms.
        result_count = 0
        for index, student, payload in students_created:
            classroom = classrooms_by_key[payload.class_key]
            class_payload = next(c for c in class_seeds if c.key == payload.class_key)
            for term_index, academic_term in enumerate(terms, start=1):
                for subject_index, subject_code in enumerate(class_payload.offered_subject_codes, start=1):
                    subject, class_subject, legacy_assignment, teacher_assignment = assignment_bundle_by_class_subject[(classroom.id, subject_code)]
                    test_score, assessment_score, exam_score = resolve_score_components(index, subject_index, term_index)
                    total_score = test_score + assessment_score + exam_score
                    grade, remark = resolve_grade(total_score)
                    session.add(StudentSubjectResult(
                        tenant_id=tenant.id,
                        student_id=student.id,
                        class_id=classroom.id,
                        subject_id=subject.id,
                        teacher_id=teacher_assignment.teacher_id,
                        class_subject_teacher_id=legacy_assignment.id,
                        teacher_assignment_id=teacher_assignment.id,
                        academic_session_id=academic_session.id,
                        academic_term_id=academic_term.id,
                        recorded_by_actor_type=ActorType.TENANT_ADMIN.value,
                        recorded_by_actor_id=tenant_admin.id,
                        test_score=test_score,
                        assessment_score=assessment_score,
                        exam_score=exam_score,
                        total_score=total_score,
                        grade=grade,
                        remark=remark,
                        status=AcademicResultStatus.SUBMITTED,
                    ))
                    result_count += 1

            if index % FLUSH_EVERY == 0:
                await session.flush()
                print(f"[{time.monotonic() - started_at:.1f}s] Created results for students: {index}/{student_count}")

        await session.flush()
        await session.commit()

        elapsed = time.monotonic() - started_at
        print("\nFull school seed complete")
        print(f"Elapsed: {elapsed:.1f}s")
        print(f"Tenant: {tenant.school_name} ({tenant.id})")
        print(f"Default password: {DEFAULT_PASSWORD}")
        print(f"Teachers: {len(teacher_batch)}")
        print(f"Parents: {len(parent_batch)}")
        print(f"Classes: {len(class_batch)}")
        print(f"Subjects: {len(subjects_by_code)}")
        print(f"Students: {len(students_created)}")
        print(f"Results: {result_count} rows ({len(terms)} terms x offered subjects x students)")
        print(f"Sample teacher login: {bulk_teacher_email(1)} / {DEFAULT_PASSWORD}")
        print(f"Sample parent login: {bulk_parent_email(1)} / {DEFAULT_PASSWORD}")
        print(f"Sample student login: {bulk_admission_number(admission_prefix, 1)} / {DEFAULT_PASSWORD}")

        # Lightweight verification against your actual auth service.
        teacher_auth = await AuthService.authenticate_actor(
            session,
            LoginRequest(identifier=bulk_teacher_email(1), password=DEFAULT_PASSWORD),
        )
        parent_auth = await AuthService.authenticate_actor(
            session,
            LoginRequest(identifier=bulk_parent_email(1), password=DEFAULT_PASSWORD),
        )
        student_auth = await AuthService.authenticate_actor(
            session,
            LoginRequest(identifier=bulk_admission_number(admission_prefix, 1), password=DEFAULT_PASSWORD),
        )
        print(
            "Verified auth:",
            f"teacher={teacher_auth.actor_type}",
            f"parent={parent_auth.actor_type}",
            f"student={student_auth.actor_type}",
        )



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed a full school workflow: teachers, parents, classes, subjects, students, assignments, and scores."
    )
    parser.add_argument("--tenant-id", help="Explicit tenant ID to seed. Required when more than one tenant exists.")
    parser.add_argument("--student-count", type=int, default=1000, help="Number of generated students. Default: 1000.")
    parser.add_argument("--teacher-count", type=int, default=None, help="Optional generated teacher count.")
    parser.add_argument("--parent-count", type=int, default=None, help="Optional generated parent count.")
    parser.add_argument(
        "--arms",
        default=",".join(DEFAULT_ARMS),
        help="Comma-separated class arms to generate. Default: A,B,C,D.",
    )
    parser.add_argument("--reset", action="store_true", help="Delete generated bulk school rows before reseeding.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    arms = [arm.strip().upper() for arm in args.arms.split(",") if arm.strip()]
    if not arms:
        raise ValueError("At least one arm is required.")
    if args.student_count < 1:
        raise ValueError("--student-count must be at least 1.")

    await seed_full_school(
        tenant_id_arg=args.tenant_id,
        student_count=args.student_count,
        teacher_count=args.teacher_count,
        parent_count=args.parent_count,
        arms=arms,
        reset=args.reset,
    )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
