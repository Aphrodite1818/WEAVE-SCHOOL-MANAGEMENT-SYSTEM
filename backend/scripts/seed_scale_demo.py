r"""Seed a fresh Weave database with scale-demo data.

Run from the backend directory:
    .\.venv\Scripts\python.exe scripts\seed_scale_demo.py
    .\.venv\Scripts\python.exe scripts\seed_scale_demo.py --schools 1 --students-per-school 50
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote_plus

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from faker import Faker
import httpx
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from starlette.datastructures import Headers, UploadFile

import app.models  # noqa: F401
from app.config.database import AsyncSessionLocal
from app.config.security import hash_password
from app.modules.classes.models import ClassRoom
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.communications.enums import (
    AnnouncementAudienceType,
    AnnouncementCategory,
    AnnouncementPriority,
    AnnouncementStatus,
    CommunicationActorType,
    NotificationSourceType,
    NotificationStatus,
)
from app.modules.media.service import MediaService
from app.modules.communications.models import (
    Announcement,
    AnnouncementAudience,
    NotificationDelivery,
)
from app.modules.parents.models import (
    ParentAccount,
    ParentAccountStatus,
    ParentMembership,
    ParentMembershipStatus,
)
from app.modules.report_cards.models import (
    ReportCard,
    ReportCardStatus,
    ReportCardSubjectLine,
)
from app.modules.school_calendar.calendar_enums import (
    SchoolCalendarDaySource,
    SchoolCalendarDayType,
    SchoolCalendarStatus,
)
from app.modules.school_calendar.models import (
    SchoolCalendar,
    SchoolCalendarConfiguration,
    SchoolCalendarDay,
)
from app.modules.student_academics.models import (
    AcademicResultStatus,
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermName,
    AcademicTermStatus,
    ClassSubject,
    ClassSubjectTeacher,
    GradingScale,
    SchoolAssessmentConfig,
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
    StudentParentLinkStatus,
    StudentProfileStatus,
)
from app.modules.subjects.models import Subject
from app.modules.subscriptions.models import TenantSubscription
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    SubscriptionStatus,
)
from app.modules.teachers.models import (
    TeacherAccount,
    TeacherAccountStatus,
    TeacherMembership,
    TeacherMembershipStatus,
)
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.tenant_management.models import (
    SubscriptionPlan,
    Tenant,
    TenantStatus,
    TenantVerificationStatus,
)


fake = Faker("en_NG")


SUBJECTS = [
    ("English Language", "ENG"),
    ("Mathematics", "MTH"),
    ("Basic Science", "BSC"),
    ("Social Studies", "SOS"),
    ("Computer Studies", "CMP"),
    ("Civic Education", "CIV"),
    ("Business Studies", "BUS"),
    ("Agricultural Science", "AGR"),
]

CLASS_NAMES = ["JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2"]
ARMS = ["A", "B"]
PREMIUM_SCHOOL_NAMES = [
    "Aurelia Crest International School",
    "Kingsbridge Meridian College",
    "The Halcyon Heights Academy",
    "Northfield Scholars Institute",
    "St. Ives Royal College",
    "Lagos Meridian Preparatory School",
    "Cedarstone International Academy",
    "The Grandview Scholars School",
    "Oakbridge Laureate College",
    "Westbourne Classical Academy",
]
LOGO_PALETTES = [
    ("0F172A", "F8FAFC"),
    ("12312B", "F8E9C4"),
    ("1E3A5F", "EAF4FF"),
    ("4C1D25", "FDEBD3"),
    ("263238", "D9F99D"),
]
GRADES = [
    (Decimal("70.00"), Decimal("100.00"), "A", "Excellent"),
    (Decimal("60.00"), Decimal("69.99"), "B", "Very good"),
    (Decimal("50.00"), Decimal("59.99"), "C", "Good"),
    (Decimal("45.00"), Decimal("49.99"), "D", "Fair"),
    (Decimal("40.00"), Decimal("44.99"), "E", "Pass"),
    (Decimal("0.00"), Decimal("39.99"), "F", "Needs improvement"),
]


def money_date(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def score(value: float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def grade_for(total: Decimal, scales: list[GradingScale]) -> GradingScale:
    for scale in scales:
        if scale.min_score <= total <= scale.max_score:
            return scale
    return scales[-1]


async def flush_chunk(db, items: list[object], chunk_size: int = 1000) -> None:
    for start in range(0, len(items), chunk_size):
        db.add_all(items[start : start + chunk_size])
        await db.flush()


def normalized(value: str | None) -> str | None:
    return value.strip().lower().replace(" ", "-") if value else None


def slugify_school_name(value: str) -> str:
    return value.lower().replace("'", "").replace(".", "").replace("&", "and").replace(" ", "-")


def premium_school_name(index: int) -> str:
    base_name = PREMIUM_SCHOOL_NAMES[(index - 1) % len(PREMIUM_SCHOOL_NAMES)]
    if index <= len(PREMIUM_SCHOOL_NAMES):
        return base_name
    return f"{base_name} Campus {index}"


def logo_initials(school_name: str) -> str:
    ignored = {"the", "of", "and", "school", "college", "academy", "international"}
    words = [word for word in school_name.replace(".", "").split() if word.lower() not in ignored]
    initials = "".join(word[0] for word in words[:3]).upper()
    return initials or "WV"


def fallback_logo_png(school_name: str, school_index: int) -> bytes:
    background, foreground = LOGO_PALETTES[(school_index - 1) % len(LOGO_PALETTES)]
    image = Image.new("RGB", (512, 512), f"#{background}")
    draw = ImageDraw.Draw(image)
    draw.ellipse((44, 44, 468, 468), outline=f"#{foreground}", width=14)
    draw.ellipse((82, 82, 430, 430), outline=f"#{foreground}", width=3)

    initials = logo_initials(school_name)
    font = ImageFont.load_default(size=112)
    bbox = draw.textbbox((0, 0), initials, font=font)
    x = (512 - (bbox[2] - bbox[0])) / 2
    y = (512 - (bbox[3] - bbox[1])) / 2 - 8
    draw.text((x, y), initials, fill=f"#{foreground}", font=font)

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


async def fetch_web_logo_png(school_name: str, school_index: int) -> bytes:
    background, foreground = LOGO_PALETTES[(school_index - 1) % len(LOGO_PALETTES)]
    initials = quote_plus(logo_initials(school_name))
    url = (
        "https://ui-avatars.com/api/"
        f"?name={initials}&size=512&background={background}&color={foreground}"
        "&format=png&bold=true&rounded=true"
    )
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "image" not in content_type.lower():
            raise ValueError(f"Logo provider returned {content_type or 'unknown content type'}")
        return response.content


async def upload_seed_logo(
    db, *, admin: TenantAdmin, school_name: str, school_index: int
) -> str | None:
    try:
        logo_bytes = await fetch_web_logo_png(school_name, school_index)
        source = "web"
    except Exception as exc:
        print(f"Logo web fetch failed for {school_name}: {exc}. Using generated fallback.")
        logo_bytes = fallback_logo_png(school_name, school_index)
        source = "generated"

    upload = UploadFile(
        file=io.BytesIO(logo_bytes),
        filename=f"{slugify_school_name(school_name)}-logo.png",
        headers=Headers({"content-type": "image/png"}),
    )
    response = await MediaService.upload_school_logo(db=db, actor=admin, file=upload)
    print(f"Uploaded {source} logo for {school_name}.")
    return response.render_url


async def seed_school(
    db,
    *,
    school_index: int,
    students_per_school: int,
    password_hash: str,
    admin_password: str,
    run_code: str,
) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    school_name = premium_school_name(school_index)
    school_key = f"{slugify_school_name(school_name)}-{run_code}-{school_index:02d}"
    session_start = date(2026, 9, 7)
    term_start = session_start
    term_end = date(2026, 12, 18)

    tenant = Tenant(
        school_name=school_name,
        slug=school_key,
        admission_number_prefix=f"WD{school_index:02d}{run_code[-4:]}",
        email=f"{school_key}@demo.weave.local",
        phone=fake.phone_number()[:20],
        address=fake.address(),
        city=fake.city(),
        state=fake.state(),
        country="Nigeria",
        status=TenantStatus.ACTIVE,
        plan=SubscriptionPlan.PROFESSIONAL,
        subscription_ends_at=money_date(365),
        max_students=students_per_school + 500,
        max_teachers=200,
        feature_flags={"announcements": True, "report_cards": True, "bulk_import": True},
        onboarding_completed=True,
        verification_status=TenantVerificationStatus.ACTIVE,
    )
    db.add(tenant)
    await db.flush()

    admin = TenantAdmin(
        tenant_id=tenant.id,
        email=f"admin.{school_key}@demo.weave.local",
        password_hash=password_hash,
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )
    db.add(admin)
    await db.flush()
    await AuthIdentityService.ensure_for_actor(
        db,
        tenant_id=tenant.id,
        payload=AuthIdentityCreate(
            identifier=admin.email,
            identifier_type=IdentifierType.EMAIL,
            actor_type=ActorType.TENANT_ADMIN,
            actor_id=admin.id,
            is_active=True,
        ),
    )

    await upload_seed_logo(db, admin=admin, school_name=school_name, school_index=school_index)

    db.add(
        TenantSubscription(
            tenant_id=tenant.id,
            plan_code=SubscriptionPlan.PROFESSIONAL,
            status=SubscriptionStatus.ACTIVE,
            billing_interval=BillingInterval.MONTHLY,
            provider=PaymentProvider.MANUAL,
            current_period_start=now,
            current_period_end=money_date(30),
            is_current=True,
            metadata_json={"seed": "scale_demo", "run_code": run_code},
            notes="Scale demo subscription seeded locally.",
        )
    )

    academic_session = AcademicSession(
        tenant_id=tenant.id,
        name="2026/2027",
        start_date=session_start,
        end_date=date(2027, 7, 23),
        status=AcademicSessionStatus.OPEN,
        is_current=True,
    )
    db.add(academic_session)
    await db.flush()

    academic_term = AcademicTerm(
        tenant_id=tenant.id,
        academic_session_id=academic_session.id,
        name=AcademicTermName.FIRST_TERM,
        start_date=term_start,
        end_date=term_end,
        status=AcademicTermStatus.OPEN,
        is_current=True,
        opened_at=now,
        opened_by_admin_id=admin.id,
    )
    db.add(academic_term)
    await db.flush()

    db.add(SchoolAssessmentConfig(tenant_id=tenant.id, test_max=20, assessment_max=20, exam_max=60))
    grading_scales = [
        GradingScale(
            tenant_id=tenant.id,
            min_score=min_score,
            max_score=max_score,
            grade=grade,
            remark=remark,
            is_active=True,
        )
        for min_score, max_score, grade, remark in GRADES
    ]
    db.add_all(grading_scales)
    await db.flush()

    teachers: list[tuple[TeacherAccount, TeacherMembership]] = []
    for index in range(1, 25):
        first_name = fake.first_name()
        last_name = fake.last_name()
        account = TeacherAccount(
            email=f"teacher{index:02d}.{school_key}@demo.weave.local",
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            phone_number=fake.phone_number()[:30],
            qualification=random.choice(["B.Ed", "B.Sc", "M.Ed", "PGDE"]),
            specialization=random.choice([name for name, _ in SUBJECTS]),
            account_status=TeacherAccountStatus.ACTIVE,
            is_verified=True,
            is_active=True,
        )
        db.add(account)
        await db.flush()
        await AuthIdentityService.ensure_for_actor(
            db,
            payload=AuthIdentityCreate(
                identifier=account.email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.TEACHER_ACCOUNT,
                actor_id=account.id,
                is_active=True,
            ),
        )
        membership = TeacherMembership(
            tenant_id=tenant.id,
            teacher_account_id=account.id,
            staff_id=f"T{school_index:02d}{index:04d}",
            job_title=random.choice(["Teacher", "Senior Teacher", "Class Teacher"]),
            department="Academics",
            employment_type="full_time",
            status=TeacherMembershipStatus.ACTIVE,
            joined_at=now - timedelta(days=random.randint(30, 900)),
        )
        db.add(membership)
        teachers.append((account, membership))
    await db.flush()

    classes: list[ClassRoom] = []
    class_by_label: dict[tuple[str, str], ClassRoom] = {}
    for class_name in CLASS_NAMES:
        for arm in ARMS:
            _, class_teacher = teachers[len(classes) % len(teachers)]
            classroom = ClassRoom(
                tenant_id=tenant.id,
                name=class_name,
                arm=arm,
                is_active=True,
                teacher_membership_id=class_teacher.id,
                is_terminal=class_name == CLASS_NAMES[-1],
            )
            classes.append(classroom)
            class_by_label[(class_name, arm)] = classroom
    db.add_all(classes)
    await db.flush()

    for index, class_name in enumerate(CLASS_NAMES[:-1]):
        for arm in ARMS:
            class_by_label[(class_name, arm)].next_class_id = class_by_label[
                (CLASS_NAMES[index + 1], arm)
            ].id
    await db.flush()

    subjects = [
        Subject(
            tenant_id=tenant.id,
            name=name,
            normalized_name=normalized(name),
            code=code,
            normalized_code=normalized(code),
            description=f"{name} curriculum for the scale demo.",
            is_active=True,
        )
        for name, code in SUBJECTS
    ]
    db.add_all(subjects)
    await db.flush()

    class_subjects: list[ClassSubject] = []
    class_subject_teachers: list[ClassSubjectTeacher] = []
    teacher_assignments: list[TeacherAssignment] = []
    teacher_by_scope = {}
    subject_by_id = {subject.id: subject for subject in subjects}
    for class_index, classroom in enumerate(classes):
        for subject_index, subject_ref in enumerate(subjects):
            _, teacher_membership = teachers[(class_index + subject_index) % len(teachers)]
            class_subject = ClassSubject(
                tenant_id=tenant.id,
                class_id=classroom.id,
                subject_id=subject_ref.id,
                is_core=subject_index < 6,
                is_active=True,
            )
            db.add(class_subject)
            await db.flush()
            teacher_link = ClassSubjectTeacher(
                tenant_id=tenant.id,
                class_id=classroom.id,
                subject_id=subject_ref.id,
                teacher_membership_id=teacher_membership.id,
                is_core=subject_index < 6,
                sort_order=subject_index + 1,
                is_active=True,
            )
            assignment = TeacherAssignment(
                tenant_id=tenant.id,
                class_subject_id=class_subject.id,
                teacher_membership_id=teacher_membership.id,
                is_active=True,
                effective_from=term_start,
            )
            class_subjects.append(class_subject)
            class_subject_teachers.append(teacher_link)
            teacher_assignments.append(assignment)
            teacher_by_scope[(classroom.id, subject_ref.id)] = (
                teacher_membership,
                teacher_link,
                assignment,
            )
    db.add_all(class_subject_teachers + teacher_assignments)
    await db.flush()

    calendar_config = SchoolCalendarConfiguration(
        tenant_id=tenant.id,
        timezone="Africa/Lagos",
        instructional_weekdays=[0, 1, 2, 3, 4],
        default_open_time=time(8, 0),
        default_close_time=time(15, 0),
        default_student_attendance_required=True,
        default_workforce_attendance_required=True,
        revision=1,
    )
    calendar = SchoolCalendar(
        tenant_id=tenant.id,
        academic_session_id=academic_session.id,
        academic_term_id=academic_term.id,
        status=SchoolCalendarStatus.ACTIVE,
        generated_at=now,
        generated_from_configuration_revision=1,
        activated_at=now,
        activated_by_admin_id=admin.id,
    )
    db.add_all([calendar_config, calendar])
    await db.flush()

    days = []
    cursor = term_start
    while cursor <= term_end:
        weekday = cursor.weekday() < 5
        days.append(
            SchoolCalendarDay(
                tenant_id=tenant.id,
                calendar_id=calendar.id,
                academic_session_id=academic_session.id,
                academic_term_id=academic_term.id,
                calendar_date=cursor,
                day_type=SchoolCalendarDayType.INSTRUCTIONAL_DAY
                if weekday
                else SchoolCalendarDayType.WEEKEND,
                title="Instructional day" if weekday else "Weekend",
                school_open=weekday,
                student_activity_allowed=weekday,
                student_attendance_required=weekday,
                workforce_attendance_required=weekday,
                opens_at=time(8, 0) if weekday else None,
                closes_at=time(15, 0) if weekday else None,
                source=SchoolCalendarDaySource.GENERATED,
                created_by_admin_id=admin.id,
            )
        )
        cursor += timedelta(days=1)
    await flush_chunk(db, days)

    students: list[Student] = []
    enrollments: list[StudentEnrollment] = []
    parents: list[ParentAccount] = []
    parent_memberships: list[ParentMembership] = []
    parent_links: list[StudentParentLink] = []
    for index in range(1, students_per_school + 1):
        classroom = classes[(index - 1) % len(classes)]
        first_name = fake.first_name()
        last_name = fake.last_name()
        student = Student(
            tenant_id=tenant.id,
            admission_number=f"{tenant.admission_number_prefix}{index:05d}",
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            account_status=StudentAccountStatus.ACTIVE,
            is_verified=True,
            is_active=True,
            password_reset_required=False,
            date_of_birth=fake.date_between(start_date="-17y", end_date="-10y"),
            gender=random.choice([Gender.MALE, Gender.FEMALE]),
            state_of_origin=fake.state(),
            admission_date=term_start,
            class_id=classroom.id,
            arm=classroom.arm,
            status=AcademicStatus.ACTIVE,
            profile_status=StudentProfileStatus.COMPLETE,
        )
        db.add(student)
        await db.flush()
        await AuthIdentityService.ensure_for_actor(
            db,
            tenant_id=tenant.id,
            payload=AuthIdentityCreate(
                identifier=student.admission_number,
                identifier_type=IdentifierType.ADMISSION_NUMBER,
                actor_type=ActorType.STUDENT,
                actor_id=student.id,
                is_active=True,
            ),
        )
        students.append(student)

        if index % 500 == 0:
            await db.flush()

    await db.flush()

    for index, student in enumerate(students, start=1):
        classroom = classes[(index - 1) % len(classes)]
        parent_first = fake.first_name()
        parent_last = student.last_name or fake.last_name()
        parent = ParentAccount(
            email=f"parent{school_index:02d}{index:05d}.{run_code}@demo.weave.local",
            password_hash=password_hash,
            first_name=parent_first,
            last_name=parent_last,
            phone_number=fake.phone_number()[:30],
            occupation=fake.job()[:150],
            address=fake.address()[:500],
            account_status=ParentAccountStatus.ACTIVE,
            is_verified=True,
            is_active=True,
        )
        db.add(parent)
        await db.flush()
        await AuthIdentityService.ensure_for_actor(
            db,
            payload=AuthIdentityCreate(
                identifier=parent.email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.PARENT_ACCOUNT,
                actor_id=parent.id,
                is_active=True,
            ),
        )
        parents.append(parent)
        enrollments.append(
            StudentEnrollment(
                tenant_id=tenant.id,
                student_id=student.id,
                class_id=classroom.id,
                academic_session_id=academic_session.id,
                started_on=term_start,
                is_current=True,
                outcome=StudentEnrollmentOutcome.ENROLLED,
                changed_by_admin_id=admin.id,
            )
        )

        if index % 500 == 0:
            await db.flush()

    await db.flush()

    for parent in parents:
        membership = ParentMembership(
            tenant_id=tenant.id,
            parent_account_id=parent.id,
            status=ParentMembershipStatus.ACTIVE,
            joined_at=now,
        )
        db.add(membership)
        parent_memberships.append(membership)
    await db.flush()

    for student, membership in zip(students, parent_memberships, strict=True):
        parent_links.append(
            StudentParentLink(
                tenant_id=tenant.id,
                student_id=student.id,
                parent_membership_id=membership.id,
                relationship_type=random.choice(
                    [
                        ParentRelationship.FATHER,
                        ParentRelationship.MOTHER,
                        ParentRelationship.GUARDIAN,
                    ]
                ),
                status=StudentParentLinkStatus.ACTIVE,
                is_primary_contact=True,
                verified_at=now,
                verified_by_type=ParentLinkVerifiedByType.TENANT_ADMIN,
                verified_by_id=admin.id,
            )
        )
    await flush_chunk(db, enrollments + parent_links)

    enrollment_by_student = {enrollment.student_id: enrollment for enrollment in enrollments}
    result_rows: list[StudentSubjectResult] = []
    report_cards: list[ReportCard] = []
    report_lines: list[ReportCardSubjectLine] = []

    core_subjects = subjects[:6]
    for position, student in enumerate(students, start=1):
        classroom = classes[(position - 1) % len(classes)]
        student_results = []
        for subject_ref in core_subjects:
            teacher_membership, teacher_link, assignment = teacher_by_scope[
                (classroom.id, subject_ref.id)
            ]
            test_score = score(random.randint(8, 20))
            assessment_score = score(random.randint(8, 20))
            exam_score = score(random.randint(24, 60))
            total = score(test_score + assessment_score + exam_score)
            scale = grade_for(total, grading_scales)
            result = StudentSubjectResult(
                tenant_id=tenant.id,
                student_id=student.id,
                class_id=classroom.id,
                subject_id=subject_ref.id,
                teacher_membership_id=teacher_membership.id,
                class_subject_teacher_id=teacher_link.id,
                teacher_assignment_id=assignment.id,
                student_enrollment_id=enrollment_by_student[student.id].id,
                academic_session_id=academic_session.id,
                academic_term_id=academic_term.id,
                grading_scale_id=scale.id,
                test_score=test_score,
                assessment_score=assessment_score,
                exam_score=exam_score,
                total_score=total,
                grade=scale.grade,
                remark=scale.remark,
                status=AcademicResultStatus.LOCKED,
                recorded_by_actor_type=CommunicationActorType.TEACHER.value,
                recorded_by_actor_id=teacher_membership.id,
                submitted_at=now,
                submitted_by_actor_type=CommunicationActorType.TEACHER.value,
                submitted_by_actor_id=teacher_membership.id,
                approved_at=now,
                approved_by_admin_id=admin.id,
                locked_at=now,
                locked_by_admin_id=admin.id,
            )
            result_rows.append(result)
            student_results.append((result, subject_ref, teacher_membership))

        total_score = score(sum(result.total_score for result, _, _ in student_results))
        average = score(total_score / Decimal(len(student_results)))
        card = ReportCard(
            tenant_id=tenant.id,
            student_id=student.id,
            class_id=classroom.id,
            academic_session_id=academic_session.id,
            academic_term_id=academic_term.id,
            total_score=total_score,
            average_score=average,
            position=position,
            position_out_of=students_per_school,
            class_teacher_comment="Steady progress through the seeded academic workflow.",
            principal_comment="Published demo report card.",
            status=ReportCardStatus.PUBLISHED,
            published_at=now,
            published_by=admin.id,
            generated_by_actor_type=CommunicationActorType.TENANT_ADMIN.value,
            generated_by_actor_id=admin.id,
        )
        report_cards.append(card)

        if position % 500 == 0:
            await db.flush()

    await flush_chunk(db, result_rows)

    for card in report_cards:
        db.add(card)
    await db.flush()

    results_by_student: dict[object, list[StudentSubjectResult]] = {}
    for result in result_rows:
        results_by_student.setdefault(result.student_id, []).append(result)

    cards_by_student = {card.student_id: card for card in report_cards}
    for result in result_rows:
        subject_ref = subject_by_id[result.subject_id]
        teacher_membership = teacher_by_scope[(result.class_id, result.subject_id)][0]
        teacher_account = next(
            account for account, membership in teachers if membership.id == teacher_membership.id
        )
        report_lines.append(
            ReportCardSubjectLine(
                tenant_id=tenant.id,
                report_card_id=cards_by_student[result.student_id].id,
                student_subject_result_id=result.id,
                subject_id=subject_ref.id,
                subject_name=subject_ref.name,
                subject_code=subject_ref.code,
                teacher_name=f"{teacher_account.first_name} {teacher_account.last_name}",
                test_score=result.test_score,
                assessment_score=result.assessment_score,
                exam_score=result.exam_score,
                total_score=result.total_score,
                grade=result.grade,
                remark=result.remark,
            )
        )
    await flush_chunk(db, report_lines)

    announcement = Announcement(
        tenant_id=tenant.id,
        created_by_actor_type=CommunicationActorType.TENANT_ADMIN,
        created_by_actor_id=admin.id,
        title="Welcome to the scale demo term",
        body="This school has seeded records for academics, calendars, parents, teachers, results, and report cards.",
        category=AnnouncementCategory.ACADEMIC,
        priority=AnnouncementPriority.NORMAL,
        status=AnnouncementStatus.PUBLISHED,
        publish_at=now,
        is_pinned=True,
    )
    db.add(announcement)
    await db.flush()
    db.add(
        AnnouncementAudience(
            tenant_id=tenant.id,
            announcement_id=announcement.id,
            audience_type=AnnouncementAudienceType.ALL_TEACHERS,
        )
    )
    db.add_all(
        [
            NotificationDelivery(
                tenant_id=tenant.id,
                recipient_actor_type=CommunicationActorType.TEACHER,
                recipient_actor_id=membership.id,
                source_type=NotificationSourceType.ANNOUNCEMENT,
                source_id=announcement.id,
                title=announcement.title,
                preview=announcement.body[:500],
                action_path=f"/announcements/{announcement.id}",
                status=NotificationStatus.UNREAD,
                delivered_at=now,
            )
            for _, membership in teachers[:10]
        ]
    )
    await db.flush()

    print(
        f"Seeded {tenant.school_name}: {students_per_school} students, "
        f"{len(teachers)} teachers, {len(parent_memberships)} parents."
    )
    return {
        "school_name": tenant.school_name,
        "tenant_id": str(tenant.id),
        "tenant_slug": tenant.slug,
        "tenant_email": tenant.email,
        "tenant_admin_id": str(admin.id),
        "tenant_admin_email": admin.email,
        "tenant_admin_password": admin_password,
        "logo_url": tenant.logo_url or "",
    }


async def repair_auth_identities(db) -> dict[str, int]:
    """Backfill canonical login identities for already-seeded demo rows."""

    counts = {
        "tenant_admins": 0,
        "teachers": 0,
        "parents": 0,
        "students": 0,
    }

    tenant_admins = (await db.scalars(select(TenantAdmin))).all()
    for admin in tenant_admins:
        await AuthIdentityService.ensure_for_actor(
            db,
            tenant_id=admin.tenant_id,
            payload=AuthIdentityCreate(
                identifier=admin.email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.TENANT_ADMIN,
                actor_id=admin.id,
                is_active=admin.is_active,
            ),
        )
        counts["tenant_admins"] += 1

    teacher_accounts = (await db.scalars(select(TeacherAccount))).all()
    for account in teacher_accounts:
        await AuthIdentityService.ensure_for_actor(
            db,
            payload=AuthIdentityCreate(
                identifier=account.email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.TEACHER_ACCOUNT,
                actor_id=account.id,
                is_active=account.is_active,
            ),
        )
        counts["teachers"] += 1

    parent_accounts = (await db.scalars(select(ParentAccount))).all()
    for account in parent_accounts:
        await AuthIdentityService.ensure_for_actor(
            db,
            payload=AuthIdentityCreate(
                identifier=account.email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.PARENT_ACCOUNT,
                actor_id=account.id,
                is_active=account.is_active,
            ),
        )
        counts["parents"] += 1

    students = (await db.scalars(select(Student))).all()
    for student in students:
        await AuthIdentityService.ensure_for_actor(
            db,
            tenant_id=student.tenant_id,
            payload=AuthIdentityCreate(
                identifier=student.admission_number,
                identifier_type=IdentifierType.ADMISSION_NUMBER,
                actor_type=ActorType.STUDENT,
                actor_id=student.id,
                is_active=student.is_active,
            ),
        )
        counts["students"] += 1

    return counts


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schools", type=int, default=5)
    parser.add_argument("--students-per-school", type=int, default=1000)
    parser.add_argument("--password", default="Password123!")
    parser.add_argument(
        "--credentials-file",
        default=str(BACKEND_DIR / "weave_demo_credentials.json"),
        help="Local ignored JSON file where seeded tenant admin credentials are written.",
    )
    parser.add_argument(
        "--run-code",
        default=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        help="Unique suffix used in demo slugs and emails.",
    )
    parser.add_argument(
        "--repair-auth-identities",
        action="store_true",
        help="Backfill auth_identities for existing rows and exit without creating new demo data.",
    )
    args = parser.parse_args()

    password_hash = hash_password(args.password)
    credentials: list[dict[str, str]] = []
    async with AsyncSessionLocal() as db:
        async with db.begin():
            if args.repair_auth_identities:
                counts = await repair_auth_identities(db)
                print(f"Repaired auth identities: {counts}")
            else:
                for school_index in range(1, args.schools + 1):
                    credentials.append(
                        await seed_school(
                            db,
                            school_index=school_index,
                            students_per_school=args.students_per_school,
                            password_hash=password_hash,
                            admin_password=args.password,
                            run_code=args.run_code,
                        )
                    )
        await AuthIdentityService.invalidate_after_commit(db)

    if args.repair_auth_identities:
        return

    credentials_path = Path(args.credentials_file)
    if not credentials_path.is_absolute():
        credentials_path = BACKEND_DIR / credentials_path
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "run_code": args.run_code,
                "tenant_admins": credentials,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote tenant admin credentials to {credentials_path}")


if __name__ == "__main__":
    asyncio.run(main())
