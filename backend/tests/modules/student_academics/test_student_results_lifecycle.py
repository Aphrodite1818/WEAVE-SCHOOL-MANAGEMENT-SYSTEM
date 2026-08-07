import pytest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    BadRequestException,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermStatus,
    TeacherAssignment,
    ClassSubjectTeacher,
    ClassSubject,
    GradingScale,
    StudentSubjectResult,
    SchoolAssessmentConfig,
    AcademicResultStatus,
)
from app.modules.student_academics.schemas import StudentSubjectResultUpsert
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import Student, StudentEnrollment
from app.modules.teachers.models import TeacherMembership
from app.modules.tenant_admins.models import TenantAdmin


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def tenant_admin():
    admin = TenantAdmin(tenant_id=uuid.uuid4())
    admin.id = uuid.uuid4()
    return admin


@pytest.fixture
def teacher():
    t = TeacherMembership(tenant_id=uuid.uuid4())
    t.id = uuid.uuid4()
    return t


@pytest.mark.asyncio
async def test_upsert_student_result_closed_session(mock_db, tenant_admin):
    # Setup mock data
    tenant_id = tenant_admin.tenant_id
    payload = StudentSubjectResultUpsert(
        student_id=uuid.uuid4(),
        academic_session_id=uuid.uuid4(),
        academic_term_id=uuid.uuid4(),
        class_subject_teacher_id=uuid.uuid4(),
        status=AcademicResultStatus.DRAFT,
    )

    assignment = TeacherAssignment(
        teacher_membership_id=uuid.uuid4(), is_active=True, id=uuid.uuid4()
    )
    compatibility = ClassSubjectTeacher(id=uuid.uuid4())
    class_subject = ClassSubject(class_id=uuid.uuid4(), subject_id=uuid.uuid4())

    student = Student(class_id=class_subject.class_id, id=uuid.uuid4())
    session = AcademicSession(
        status=AcademicSessionStatus.CLOSED, is_current=False, id=uuid.uuid4()
    )
    term = AcademicTerm(
        academic_session_id=session.id,
        status=AcademicTermStatus.CLOSED,
        is_current=False,
        id=uuid.uuid4(),
    )

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicService._resolve_assignment_context",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.modules.students.repository.StudentRepository.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_student,
        patch(
            "app.modules.student_academics.repository.StudentAcademicRepository.get_academic_session_by_id",
            new_callable=AsyncMock,
        ) as mock_get_session,
        patch(
            "app.modules.student_academics.repository.StudentAcademicRepository.get_term_by_id",
            new_callable=AsyncMock,
        ) as mock_get_term,
    ):
        mock_resolve.return_value = (assignment, compatibility, class_subject)
        mock_get_student.return_value = student
        mock_get_session.return_value = session
        mock_get_term.return_value = term

        with pytest.raises(
            ConflictException,
            match="Results can only be modified in the current open session.",
        ):
            await StudentAcademicService.upsert_student_result(mock_db, tenant_admin, payload)


@pytest.mark.asyncio
async def test_upsert_student_result_not_enrolled(mock_db, tenant_admin):
    tenant_id = tenant_admin.tenant_id
    payload = StudentSubjectResultUpsert(
        student_id=uuid.uuid4(),
        academic_session_id=uuid.uuid4(),
        academic_term_id=uuid.uuid4(),
        class_subject_teacher_id=uuid.uuid4(),
        status=AcademicResultStatus.DRAFT,
    )

    assignment = TeacherAssignment(
        teacher_membership_id=uuid.uuid4(), is_active=True, id=uuid.uuid4()
    )
    compatibility = ClassSubjectTeacher(id=uuid.uuid4())
    class_subject = ClassSubject(class_id=uuid.uuid4(), subject_id=uuid.uuid4())

    student = Student(class_id=uuid.uuid4(), id=uuid.uuid4())  # Mismatched class
    session = AcademicSession(status=AcademicSessionStatus.OPEN, is_current=True, id=uuid.uuid4())
    term = AcademicTerm(
        academic_session_id=session.id,
        status=AcademicTermStatus.OPEN,
        is_current=True,
        id=uuid.uuid4(),
    )
    enrollment = StudentEnrollment(
        class_id=uuid.uuid4(), academic_session_id=session.id, id=uuid.uuid4()
    )  # Mismatched class

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicService._resolve_assignment_context",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "app.modules.students.repository.StudentRepository.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_student,
        patch(
            "app.modules.student_academics.repository.StudentAcademicRepository.get_academic_session_by_id",
            new_callable=AsyncMock,
        ) as mock_get_session,
        patch(
            "app.modules.student_academics.repository.StudentAcademicRepository.get_term_by_id",
            new_callable=AsyncMock,
        ) as mock_get_term,
        patch(
            "app.modules.students.repository.StudentEnrollmentRepository.get_current",
            new_callable=AsyncMock,
        ) as mock_get_current,
    ):
        mock_resolve.return_value = (assignment, compatibility, class_subject)
        mock_get_student.return_value = student
        mock_get_session.return_value = session
        mock_get_term.return_value = term
        mock_get_current.return_value = enrollment

        with pytest.raises(
            ForbiddenException,
            match="Student is not enrolled in the assigned class for this session.",
        ):
            await StudentAcademicService.upsert_student_result(mock_db, tenant_admin, payload)


@pytest.mark.asyncio
async def test_update_grading_scale_blocks_active(mock_db, tenant_admin):
    from app.modules.student_academics.schemas import GradingScaleUpdate

    scale = GradingScale(is_active=True, min_score=Decimal("0.0"), max_score=Decimal("10.0"))

    with patch(
        "app.modules.student_academics.repository.StudentAcademicRepository.get_grading_scale_by_id",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = scale
        payload = GradingScaleUpdate(grade="A")
        with pytest.raises(ConflictException, match="Active grading scales cannot be modified."):
            await StudentAcademicService.update_grading_scale(
                mock_db, tenant_admin.tenant_id, uuid.uuid4(), payload
            )
