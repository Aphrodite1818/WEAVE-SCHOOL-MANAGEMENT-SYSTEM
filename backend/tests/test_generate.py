import pytest
import uuid
from app.core.exceptions import BadRequestException
from app.modules.report_cards.generation_service import EnrollmentReportCardService
from app.modules.report_cards.schemas import ReportCardGenerateRequest
from app.modules.tenant_admins.models import TenantAdmin
from app.modules.students.models import StudentEnrollment
from app.modules.student_academics.models import AcademicTerm, StudentSubjectResult
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.report_cards.service import ReportCardService
from sqlalchemy import select
from decimal import Decimal

@pytest.mark.asyncio
async def test_generate_report_card(db_session):
    result = await db_session.execute(select(StudentEnrollment).limit(1))
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        pytest.skip("No enrollments to test")

    term_res = await db_session.execute(select(AcademicTerm).where(AcademicTerm.academic_session_id == enrollment.academic_session_id).limit(1))
    term = term_res.scalar_one_or_none()
    if not term:
        pytest.skip("No terms found for session")

    admin = TenantAdmin(tenant_id=enrollment.tenant_id)
    admin.id = uuid.uuid4()
    
    payload = ReportCardGenerateRequest(
        academic_session_id=enrollment.academic_session_id,
        academic_term_id=term.id,
        student_id=enrollment.student_id,
    )
    
    try:
        await EnrollmentReportCardService.generate(db_session, admin, payload)
    except Exception as e:
        pytest.fail(f"Generate raised an exception: {repr(e)}")
