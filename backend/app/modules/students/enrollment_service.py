"""Focused student enrollment history service.

Class-change writes remain in the canonical student service; this module keeps
history response construction isolated and avoids coupling display enrichment
to lifecycle mutations.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.classes.repository import ClassRoomRepository
from app.modules.student_academics.lifecycle_repository import (
    AcademicSessionLifecycleRepository,
)
from app.modules.students.repository import (
    StudentEnrollmentRepository,
    StudentRepository,
)
from app.modules.students.schemas import StudentEnrollmentDetailResponse
from app.modules.students.service import (
    StudentEnrollmentService as StudentEnrollmentMutationService,
)


class StudentEnrollmentService(StudentEnrollmentMutationService):
    """Enrollment history reads plus inherited class-change mutations."""

    @staticmethod
    async def list_history(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[StudentEnrollmentDetailResponse]:
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")

        rows = await StudentEnrollmentRepository.list_for_student(
            db,
            tenant_id,
            student_id,
        )
        output: list[StudentEnrollmentDetailResponse] = []
        for row in rows:
            classroom = await ClassRoomRepository.get_by_id(
                db,
                tenant_id,
                row.class_id,
            )
            session = await AcademicSessionLifecycleRepository.get_by_id(
                db,
                tenant_id,
                row.academic_session_id,
            )
            base = StudentEnrollmentDetailResponse.model_validate(row)
            output.append(
                base.model_copy(
                    update={
                        "class_name": classroom.name if classroom else None,
                        "class_arm": classroom.arm if classroom else None,
                        "academic_session_name": (session.name if session else None),
                    }
                )
            )
        return output
