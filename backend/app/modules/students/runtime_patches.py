"""Runtime safety patch for the student access-code flow.

This keeps the existing service behavior but fixes two small issues from the
student password-reset integration:

1. Persist state_of_origin after student creation.
2. Disable the old student password when an admin generates a reset code.

The patch is applied once from app.main during application creation.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.students.models import StudentAccessCodePurpose
from app.modules.students.repository import StudentRepository
from app.modules.students.schemas import (
    StudentAdminAccessCodeResponse,
    StudentCreate,
    StudentResponse,
)
from app.modules.students.service import StudentService
from app.modules.tenant_admins.models import TenantAdmin


_PATCH_APPLIED_ATTR = "_student_access_code_runtime_patch_applied"


def apply_student_runtime_patches() -> None:
    """Apply student access-code flow fixes once."""

    if getattr(StudentService, _PATCH_APPLIED_ATTR, False):
        return

    original_create_student_profile = StudentService.create_student_profile

    async def create_student_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: StudentCreate,
    ) -> StudentResponse:
        """Create a student and persist optional admin-only profile fields."""

        response = await original_create_student_profile(
            db=db,
            actor=actor,
            payload=payload,
        )

        state_of_origin = getattr(payload, "state_of_origin", None)
        if not state_of_origin:
            return response

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=response.id,
        )
        if student is None:
            return response

        student.state_of_origin = state_of_origin
        updated_student = await StudentRepository.save(db=db, student=student)
        await db.commit()
        await db.refresh(updated_student)

        return StudentResponse.model_validate(updated_student).model_copy(
            update={
                "setup_code": response.setup_code,
                "access_code_expires_at": response.access_code_expires_at,
            }
        )

    async def admin_reset_student_access_code(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
    ) -> StudentAdminAccessCodeResponse:
        """Generate a reset access code and disable the previous password."""

        StudentService._ensure_tenant_admin(actor)

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
        )
        if student is None:
            from app.core.exceptions import NotFoundException

            raise NotFoundException(detail="Student profile not found")

        plain_code, access_code = await StudentService._create_student_access_code(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student.id,
            purpose=StudentAccessCodePurpose.PASSWORD_RESET,
            created_by_admin_id=actor.id,
        )

        student.password_hash = None
        student.password_reset_required = True
        updated_student = await StudentRepository.save(db=db, student=student)

        await db.commit()
        await db.refresh(updated_student)

        return StudentAdminAccessCodeResponse(
            student_id=updated_student.id,
            admission_number=updated_student.admission_number,
            full_name=StudentService._student_full_name(updated_student),
            purpose=StudentAccessCodePurpose.PASSWORD_RESET,
            access_code=plain_code,
            expires_at=access_code.expires_at,
        )

    StudentService.create_student_profile = staticmethod(create_student_profile)
    StudentService.admin_reset_student_access_code = staticmethod(
        admin_reset_student_access_code
    )
    setattr(StudentService, _PATCH_APPLIED_ATTR, True)
