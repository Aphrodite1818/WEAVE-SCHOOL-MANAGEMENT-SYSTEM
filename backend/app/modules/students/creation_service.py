"""Tenant-admin student creation workflow."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth_identity.service import AuthIdentityService
from app.modules.students.schemas import StudentCreate, StudentDetailResponse
from app.modules.students.service import StudentService
from app.modules.tenant_admins.models import TenantAdmin


class StudentCreationService:
    """Create students only after the school has completed onboarding."""

    @staticmethod
    async def create_student_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: StudentCreate,
    ) -> StudentDetailResponse:
        """Create student, enrollment, setup code, invitations, and email jobs."""

        try:
            created = await StudentService._create_student_with_lifecycle(
                db,
                actor=actor,
                payload=payload,
                invitation_source="student_creation",
            )
            await db.commit()
            await AuthIdentityService.invalidate_after_commit(db)
        except Exception:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)
            raise

        await db.refresh(created.student)
        detail = await StudentService._build_detail_response(db, created.student)
        return detail.model_copy(
            update={
                "setup_code": created.setup_code,
                "access_code_expires_at": created.access_code_expires_at,
            }
        )
