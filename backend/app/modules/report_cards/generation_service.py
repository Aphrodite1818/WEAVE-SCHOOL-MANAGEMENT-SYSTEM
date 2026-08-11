from __future__ import annotations

import uuid
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.report_cards.schemas import (
    ReportCardBulkGenerateResponse,
    ReportCardClassOverviewResponse,
    ReportCardClassOverviewRow,
    ReportCardGenerateRequest,
    ReportCardResponse,
)
from app.modules.report_cards.service import ReportCardService
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.students.models import StudentEnrollment
from app.modules.students.repository import StudentRepository
from app.modules.tenant_admins.models import TenantAdmin


class EnrollmentReportCardService:
    """Report-card generation that treats StudentEnrollment as the class source of truth."""

    @staticmethod
    async def _validate_period(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> None:
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, tenant_id, academic_session_id
        )
        term = await StudentAcademicRepository.get_term_by_id(db, tenant_id, academic_term_id)
        if session is None:
            raise NotFoundException("Academic session not found.")
        if term is None or term.academic_session_id != academic_session_id:
            raise BadRequestException("The selected term does not belong to the selected session.")

    @staticmethod
    async def _enrollment_for_student_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> StudentEnrollment | None:
        return (
            await db.execute(
                select(StudentEnrollment)
                .where(
                    StudentEnrollment.tenant_id == tenant_id,
                    StudentEnrollment.student_id == student_id,
                    StudentEnrollment.academic_session_id == academic_session_id,
                )
                .order_by(
                    StudentEnrollment.is_current.desc(),
                    StudentEnrollment.started_on.desc(),
                    StudentEnrollment.created_at.desc(),
                )
                .limit(1)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def _enrollments_for_class_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> list[StudentEnrollment]:
        rows = (
            (
                await db.execute(
                    select(StudentEnrollment)
                    .where(
                        StudentEnrollment.tenant_id == tenant_id,
                        StudentEnrollment.class_id == class_id,
                        StudentEnrollment.academic_session_id == academic_session_id,
                    )
                    .order_by(
                        StudentEnrollment.student_id,
                        StudentEnrollment.is_current.desc(),
                        StudentEnrollment.started_on.desc(),
                        StudentEnrollment.created_at.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        latest_by_student: dict[uuid.UUID, StudentEnrollment] = {}
        for enrollment in rows:
            latest_by_student.setdefault(enrollment.student_id, enrollment)
        return list(latest_by_student.values())

    @staticmethod
    async def _generate_one(
        db: AsyncSession,
        actor: TenantAdmin,
        *,
        student_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
        commit: bool,
    ) -> ReportCardResponse:
        student = await StudentRepository.get_student_by_id(db, actor.tenant_id, student_id)
        if student is None:
            raise NotFoundException("Student not found.")

        enrollment = await EnrollmentReportCardService._enrollment_for_student_session(
            db,
            actor.tenant_id,
            student_id,
            academic_session_id,
        )
        if enrollment is None:
            raise BadRequestException(
                "The student has no enrollment for the selected academic session."
            )

        results = await ReportCardService._finalized_results_for_student(
            db,
            actor.tenant_id,
            student_id,
            academic_session_id,
            academic_term_id,
        )
        if not results:
            raise BadRequestException("No locked scores are available for this student.")

        existing = await ReportCardRepository.get_by_student_period(
            db,
            actor.tenant_id,
            student_id,
            academic_session_id,
            academic_term_id,
        )
        if existing is not None and not existing.is_outdated:
            raise BadRequestException(
                "A current report card already exists for this student and academic period."
            )

        enrollment_student = SimpleNamespace(
            id=student.id,
            class_id=enrollment.class_id,
        )
        card = await ReportCardService._create_card_from_results(
            db,
            actor,
            enrollment_student,
            academic_session_id,
            academic_term_id,
            results,
            replace_existing=existing if existing is not None else None,
        )
        await ReportCardService._apply_class_positions(
            db,
            actor.tenant_id,
            enrollment.class_id,
            academic_session_id,
            academic_term_id,
        )
        if commit:
            await db.commit()
        return await ReportCardService.get(db, actor, card.id)

    @staticmethod
    async def generate(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ReportCardGenerateRequest,
    ) -> ReportCardResponse | ReportCardBulkGenerateResponse:
        await EnrollmentReportCardService._validate_period(
            db,
            actor.tenant_id,
            payload.academic_session_id,
            payload.academic_term_id,
        )

        if payload.student_id is not None:
            return await EnrollmentReportCardService._generate_one(
                db,
                actor,
                student_id=payload.student_id,
                academic_session_id=payload.academic_session_id,
                academic_term_id=payload.academic_term_id,
                commit=True,
            )

        enrollments = await EnrollmentReportCardService._enrollments_for_class_session(
            db,
            actor.tenant_id,
            payload.class_id,
            payload.academic_session_id,
        )
        if not enrollments:
            raise BadRequestException(
                "No students are enrolled in this class for the selected session."
            )

        generated: list[ReportCardResponse] = []
        skipped: list[dict] = []
        for enrollment in enrollments:
            try:
                async with db.begin_nested():
                    card = await EnrollmentReportCardService._generate_one(
                        db,
                        actor,
                        student_id=enrollment.student_id,
                        academic_session_id=payload.academic_session_id,
                        academic_term_id=payload.academic_term_id,
                        commit=False,
                    )
                generated.append(card)
            except (BadRequestException, NotFoundException) as exc:
                skipped.append(
                    {
                        "student_id": str(enrollment.student_id),
                        "reason": str(exc),
                    }
                )

        await ReportCardService._apply_class_positions(
            db,
            actor.tenant_id,
            payload.class_id,
            payload.academic_session_id,
            payload.academic_term_id,
        )
        await db.commit()
        return ReportCardBulkGenerateResponse(generated=generated, skipped=skipped)

    @staticmethod
    async def class_overview(
        db: AsyncSession,
        actor: TenantAdmin,
        *,
        class_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> ReportCardClassOverviewResponse:
        await EnrollmentReportCardService._validate_period(
            db,
            actor.tenant_id,
            academic_session_id,
            academic_term_id,
        )
        expected = await ReportCardService._expected_level_subjects(db, actor.tenant_id, class_id)
        enrollments = await EnrollmentReportCardService._enrollments_for_class_session(
            db,
            actor.tenant_id,
            class_id,
            academic_session_id,
        )
        cards = await ReportCardRepository.list_active_cards_for_class_period(
            db,
            actor.tenant_id,
            class_id,
            academic_session_id,
            academic_term_id,
        )
        cards_by_student = {card.student_id: card for card in cards}

        rows: list[ReportCardClassOverviewRow] = []
        for enrollment in enrollments:
            student = await StudentRepository.get_student_by_id(
                db,
                actor.tenant_id,
                enrollment.student_id,
            )
            if student is None:
                continue
            locked = await ReportCardService._finalized_results_for_student(
                db,
                actor.tenant_id,
                student.id,
                academic_session_id,
                academic_term_id,
            )
            missing = await ReportCardService._missing_subjects(
                db,
                actor.tenant_id,
                class_id,
                student.id,
                academic_session_id,
                academic_term_id,
            )
            card = cards_by_student.get(student.id)
            rows.append(
                ReportCardClassOverviewRow(
                    student_id=student.id,
                    student_name=(
                        " ".join(
                            part for part in [student.first_name, student.last_name] if part
                        ).strip()
                        or None
                    ),
                    admission_number=student.admission_number,
                    submitted_count=len(locked),
                    expected_count=len(expected),
                    report_card_id=card.id if card else None,
                    report_card_status=card.status.value if card else None,
                    report_card_version=card.version if card else None,
                    is_outdated=card.is_outdated if card else False,
                    missing_subject_names=missing,
                )
            )

        return ReportCardClassOverviewResponse(
            class_id=class_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            expected_subject_count=len(expected),
            items=rows,
        )
