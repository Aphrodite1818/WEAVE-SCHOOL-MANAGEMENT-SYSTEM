"""Smoke and orchestration tests for enrollment-based report-card generation."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.exceptions import BadRequestException
from app.modules.report_cards.generation_service import (
    EnrollmentReportCardService,
)
from app.modules.report_cards.schemas import ReportCardGenerateRequest, ReportCardResponse
from app.modules.report_cards.service import ReportCardService
from app.modules.student_academics.models import AcademicTerm
from app.modules.students.models import StudentEnrollment
from app.modules.tenant_admins.models import TenantAdmin


@pytest.mark.asyncio
async def test_generate_report_card_respects_locked_score_requirement(
    db_session,
) -> None:
    enrollment_result = await db_session.execute(select(StudentEnrollment).limit(1))
    enrollment = enrollment_result.scalar_one_or_none()

    if enrollment is None:
        pytest.skip("No enrollments are available for the smoke test.")

    term_result = await db_session.execute(
        select(AcademicTerm)
        .where(AcademicTerm.academic_session_id == enrollment.academic_session_id)
        .limit(1)
    )
    term = term_result.scalar_one_or_none()

    if term is None:
        pytest.skip("No academic term exists for the selected enrollment.")

    admin = TenantAdmin(
        tenant_id=enrollment.tenant_id,
    )
    admin.id = uuid.uuid4()

    payload = ReportCardGenerateRequest(
        academic_session_id=enrollment.academic_session_id,
        academic_term_id=term.id,
        student_id=enrollment.student_id,
    )

    locked_results = await ReportCardService._finalized_results_for_student(
        db_session,
        enrollment.tenant_id,
        enrollment.student_id,
        enrollment.academic_session_id,
        term.id,
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


class _NestedTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_bulk_generate_applies_class_positions_once_after_all_students(
    monkeypatch,
) -> None:
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    session_id = uuid.uuid4()
    term_id = uuid.uuid4()
    student_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

    admin = TenantAdmin(tenant_id=tenant_id)
    admin.id = uuid.uuid4()
    payload = ReportCardGenerateRequest(
        class_id=class_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
    )

    validate_period = AsyncMock()
    enrollments_for_class = AsyncMock(
        return_value=[SimpleNamespace(student_id=student_id) for student_id in student_ids]
    )
    generate_one = AsyncMock(
        side_effect=[
            ReportCardResponse.model_construct(id=uuid.uuid4()) for _ in student_ids
        ]
    )
    apply_positions = AsyncMock()

    monkeypatch.setattr(EnrollmentReportCardService, "_validate_period", validate_period)
    monkeypatch.setattr(
        EnrollmentReportCardService,
        "_enrollments_for_class_session",
        enrollments_for_class,
    )
    monkeypatch.setattr(EnrollmentReportCardService, "_generate_one", generate_one)
    monkeypatch.setattr(ReportCardService, "_apply_class_positions", apply_positions)

    db = SimpleNamespace(
        begin_nested=lambda: _NestedTransaction(),
        commit=AsyncMock(),
    )

    result = await EnrollmentReportCardService.generate(db, admin, payload)

    assert len(result.generated) == len(student_ids)
    assert result.skipped == []
    assert generate_one.await_count == len(student_ids)
    assert all(
        call.kwargs["apply_positions"] is False
        for call in generate_one.await_args_list
    )
    apply_positions.assert_awaited_once_with(
        db,
        tenant_id,
        class_id,
        session_id,
        term_id,
    )
    db.commit.assert_awaited_once()
