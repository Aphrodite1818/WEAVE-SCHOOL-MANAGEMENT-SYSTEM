from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy import delete, select

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.config.database import AsyncSessionLocal, engine
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import AuthService
from app.modules.auth_identity.models import ActorType
from app.modules.report_cards.models import ReportCard, ReportCardStatus, ReportCardSubjectLine
from app.modules.student_academics.models import AcademicResultStatus, AcademicSession, AcademicTerm, AcademicTermName, StudentSubjectResult
from app.modules.students.models import Student
from app.modules.subjects.models import Subject
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin
from seed_current_tenant_dummy_data import DEFAULT_PASSWORD, resolve_target_tenant, seed as seed_base_demo


DECIMAL_PLACES = Decimal("0.01")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(DECIMAL_PLACES, rounding=ROUND_HALF_UP)


async def scalar_one_or_none(session, statement):
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def ensure_some_draft_results(session, *, tenant_id: uuid.UUID, max_drafts: int) -> int:
    """Leave a few result rows in draft so dashboards show realistic pending work."""

    if max_drafts <= 0:
        return 0

    result = await session.execute(
        select(StudentSubjectResult)
        .where(StudentSubjectResult.tenant_id == tenant_id)
        .order_by(StudentSubjectResult.created_at.desc())
        .limit(max_drafts)
    )
    rows = list(result.scalars().all())

    for row in rows:
        row.status = AcademicResultStatus.DRAFT

    await session.flush()
    return len(rows)


async def ensure_report_card(
    session,
    *,
    tenant_id: uuid.UUID,
    student: Student,
    results: list[StudentSubjectResult],
    academic_session: AcademicSession,
    academic_term: AcademicTerm,
    tenant_admin: TenantAdmin,
    position: int,
    position_out_of: int,
    should_publish: bool,
) -> ReportCard | None:
    submitted_results = [row for row in results if row.status == AcademicResultStatus.SUBMITTED]
    if not submitted_results:
        return None

    total_score = money(sum((Decimal(row.total_score or 0) for row in submitted_results), Decimal("0")))
    average_score = money(total_score / Decimal(len(submitted_results)))

    report_card = await scalar_one_or_none(
        session,
        select(ReportCard).where(
            ReportCard.tenant_id == tenant_id,
            ReportCard.student_id == student.id,
            ReportCard.academic_session_id == academic_session.id,
            ReportCard.academic_term_id == academic_term.id,
            ReportCard.superseded_at.is_(None),
        ),
    )

    if report_card is None:
        report_card = ReportCard(
            tenant_id=tenant_id,
            student_id=student.id,
            class_id=student.class_id,
            academic_session_id=academic_session.id,
            academic_term_id=academic_term.id,
            total_score=total_score,
            average_score=average_score,
            position=position,
            position_out_of=position_out_of,
            class_teacher_comment="Good performance. Keep improving consistency across all subjects.",
            principal_comment="Promoted effort and discipline noted. Maintain steady academic focus.",
            generated_by_actor_type=ActorType.TENANT_ADMIN.value,
            generated_by_actor_id=tenant_admin.id,
            status=ReportCardStatus.PUBLISHED if should_publish else ReportCardStatus.DRAFT,
            published_at=datetime.now(UTC) if should_publish else None,
            published_by=tenant_admin.id if should_publish else None,
        )
        session.add(report_card)
        await session.flush()
    else:
        report_card.class_id = student.class_id
        report_card.total_score = total_score
        report_card.average_score = average_score
        report_card.position = position
        report_card.position_out_of = position_out_of
        report_card.class_teacher_comment = "Good performance. Keep improving consistency across all subjects."
        report_card.principal_comment = "Promoted effort and discipline noted. Maintain steady academic focus."
        report_card.generated_by_actor_type = ActorType.TENANT_ADMIN.value
        report_card.generated_by_actor_id = tenant_admin.id
        report_card.status = ReportCardStatus.PUBLISHED if should_publish else ReportCardStatus.DRAFT
        report_card.published_at = datetime.now(UTC) if should_publish else None
        report_card.published_by = tenant_admin.id if should_publish else None
        await session.flush()

    await session.execute(
        delete(ReportCardSubjectLine).where(ReportCardSubjectLine.report_card_id == report_card.id)
    )

    for row in submitted_results:
        subject = await session.get(Subject, row.subject_id)
        teacher = await session.get(Teacher, row.teacher_id)
        teacher_name = None
        if teacher is not None:
            teacher_name = " ".join([teacher.first_name or "", teacher.last_name or ""]).strip() or teacher.email

        session.add(
            ReportCardSubjectLine(
                tenant_id=tenant_id,
                report_card_id=report_card.id,
                student_subject_result_id=row.id,
                subject_id=row.subject_id,
                subject_name=subject.name if subject is not None else "Subject",
                subject_code=subject.code if subject is not None else None,
                teacher_name=teacher_name,
                test_score=money(row.test_score or 0),
                assessment_score=money(row.assessment_score or 0),
                exam_score=money(row.exam_score or 0),
                total_score=money(row.total_score or 0),
                grade=row.grade or "--",
                remark=row.remark,
            )
        )

    await session.flush()
    return report_card


async def seed_report_cards_and_dashboard_status(*, tenant_id_arg: str | None, max_drafts: int) -> None:
    async with AsyncSessionLocal() as session:
        tenant = await resolve_target_tenant(session, tenant_id_arg)
        tenant_admin = await scalar_one_or_none(
            session,
            select(TenantAdmin).where(TenantAdmin.tenant_id == tenant.id).order_by(TenantAdmin.created_at.asc()),
        )
        if tenant_admin is None:
            raise ValueError("Tenant has no tenant_admin record. Create/login tenant admin before seeding demo data.")

        academic_session = await scalar_one_or_none(
            session,
            select(AcademicSession).where(
                AcademicSession.tenant_id == tenant.id,
                AcademicSession.name == "2025/2026",
            ),
        )
        if academic_session is None:
            raise ValueError("Academic session was not seeded. Run without --skip-base first.")

        academic_term = await scalar_one_or_none(
            session,
            select(AcademicTerm).where(
                AcademicTerm.tenant_id == tenant.id,
                AcademicTerm.academic_session_id == academic_session.id,
                AcademicTerm.name == AcademicTermName.THIRD_TERM,
            ),
        )
        if academic_term is None:
            raise ValueError("Academic term was not seeded. Run without --skip-base first.")

        draft_count = await ensure_some_draft_results(session, tenant_id=tenant.id, max_drafts=max_drafts)

        result = await session.execute(
            select(StudentSubjectResult).where(
                StudentSubjectResult.tenant_id == tenant.id,
                StudentSubjectResult.academic_session_id == academic_session.id,
                StudentSubjectResult.academic_term_id == academic_term.id,
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
            average = money(
                sum((Decimal(row.total_score or 0) for row in submitted_rows), Decimal("0"))
                / Decimal(len(submitted_rows))
            )
            student_averages.append((student, average))

        students_by_class: dict[uuid.UUID, list[tuple[Student, Decimal]]] = defaultdict(list)
        for student, average in student_averages:
            students_by_class[student.class_id].append((student, average))

        position_map: dict[uuid.UUID, tuple[int, int]] = {}
        for _class_id, class_rows in students_by_class.items():
            ranked_rows = sorted(class_rows, key=lambda item: item[1], reverse=True)
            out_of = len(ranked_rows)
            for position, (student, _average) in enumerate(ranked_rows, start=1):
                position_map[student.id] = (position, out_of)

        generated_count = 0
        published_count = 0
        for index, (student, _average) in enumerate(student_averages, start=1):
            position, out_of = position_map[student.id]
            should_publish = index % 4 != 0
            card = await ensure_report_card(
                session,
                tenant_id=tenant.id,
                student=student,
                results=results_by_student[student.id],
                academic_session=academic_session,
                academic_term=academic_term,
                tenant_admin=tenant_admin,
                position=position,
                position_out_of=out_of,
                should_publish=should_publish,
            )
            if card is not None:
                generated_count += 1
                if card.status == ReportCardStatus.PUBLISHED:
                    published_count += 1

        await session.commit()

    print("Full dashboard demo data is ready.")
    print(f"Tenant ID: {tenant.id}")
    print(f"Default login password: {DEFAULT_PASSWORD}")
    print(f"Draft result rows left pending: {draft_count}")
    print(f"Report cards generated: {generated_count}")
    print(f"Report cards published: {published_count}")
    print("Teacher login: testteacher1@gmail.com")
    print("Parent login: testparent1@gmail.com")
    print(f"Student login starts from: {(tenant.admission_number_prefix or 'DBS')}2600001")


async def verify_demo_logins(tenant_id_arg: str | None) -> None:
    async with AsyncSessionLocal() as session:
        tenant = await resolve_target_tenant(session, tenant_id_arg)
        prefix = tenant.admission_number_prefix or "DBS"
        teacher_auth = await AuthService.authenticate_actor(
            session,
            LoginRequest(identifier="testteacher1@gmail.com", password=DEFAULT_PASSWORD),
        )
        parent_auth = await AuthService.authenticate_actor(
            session,
            LoginRequest(identifier="testparent1@gmail.com", password=DEFAULT_PASSWORD),
        )
        student_auth = await AuthService.authenticate_actor(
            session,
            LoginRequest(identifier=f"{prefix}2600001", password=DEFAULT_PASSWORD),
        )
        print(
            "Verified demo logins:",
            f"teacher={teacher_auth.actor_type}",
            f"parent={parent_auth.actor_type}",
            f"student={student_auth.actor_type}",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a tenant with enough demo data to exercise every dashboard.")
    parser.add_argument("--tenant-id", help="Explicit tenant ID. Required when more than one tenant exists.")
    parser.add_argument("--skip-base", action="store_true", help="Skip base teachers/classes/students/results seed and only add report-card/dashboard finishing data.")
    parser.add_argument("--draft-results", type=int, default=4, help="Number of result rows to leave in draft so pending metrics are visible.")
    parser.add_argument("--no-login-check", action="store_true", help="Skip demo login verification after seeding.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    if not args.skip_base:
        await seed_base_demo(args.tenant_id)

    await seed_report_cards_and_dashboard_status(
        tenant_id_arg=args.tenant_id,
        max_drafts=max(args.draft_results, 0),
    )

    if not args.no_login_check:
        await verify_demo_logins(args.tenant_id)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
