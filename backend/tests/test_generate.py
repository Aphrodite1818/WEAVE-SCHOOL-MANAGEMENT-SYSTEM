"""Smoke tests for enrollment-based report-card generation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import BadRequestException
from app.modules.report_cards.generation_service import (
    EnrollmentReportCardService,
)
from app.modules.report_cards.schemas import ReportCardGenerateRequest
from app.modules.report_cards.service import ReportCardService
from app.modules.student_academics.models import AcademicTerm
from app.modules.students.models import StudentEnrollment
from app.modules.tenant_admins.models import TenantAdmin


@pytest.mark.asyncio
async def test_generate_report_card_respects_locked_score_requirement(
    db_session,
) -> None:
    enrollment_result = await db_session.execute(
        select(StudentEnrollment).limit(1)
    )
    enrollment = enrollment_result.scalar_one_or_none()

    if enrollment is None:
        pytest.skip("No enrollments are available for the smoke test.")

    term_result = await db_session.execute(
        select(AcademicTerm)
        .where(
            AcademicTerm.academic_session_id
            == enrollment.academic_session_id
        )
        .limit(1)
    )
    term = term_result.scalar_one_or_none()

    if term is None:
        pytest.skip(
            "No academic term exists for the selected enrollment."
        )

    admin = TenantAdmin(
        tenant_id=enrollment.tenant_id,
    )
    admin.id = uuid.uuid4()

    payload = ReportCardGenerateRequest(
        academic_session_id=enrollment.academic_session_id,
        academic_term_id=term.id,
        student_id=enrollment.student_id,
    )

    locked_results = (
        await ReportCardService._finalized_results_for_student(
            db_session,
            enrollment.tenant_id,
            enrollment.student_id,
            enrollment.academic_session_id,
            term.id,
        )
    )

    if not locked_results:
        with pytest.raises(
            BadRequestException,
            match="No locked scores are available",
        ):
            await EnrollmentReportCardService.generate(
                db_session,
                admin,
                payload,
            )
        return

    generated = await EnrollmentReportCardService.generate(
        db_session,
        admin,
        payload,
    )

    assert generated is not None
