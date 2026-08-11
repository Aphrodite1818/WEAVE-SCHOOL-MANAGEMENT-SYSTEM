from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import ForbiddenException
from app.modules.student_academics.models import AcademicResultStatus
from app.modules.student_academics.schemas import StudentSubjectResultUpsert
from app.modules.student_academics.service import StudentAcademicService
from app.modules.teachers.models import TeacherMembership


@pytest.mark.asyncio
async def test_teacher_result_mutation_is_unconditionally_forbidden() -> None:
    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    payload = StudentSubjectResultUpsert(
        student_id=uuid4(),
        teacher_assignment_id=uuid4(),
        academic_session_id=uuid4(),
        academic_term_id=uuid4(),
        status=AcademicResultStatus.DRAFT,
    )
    with pytest.raises(ForbiddenException, match="read-only"):
        await StudentAcademicService.upsert_student_result(SimpleNamespace(), teacher, payload)
