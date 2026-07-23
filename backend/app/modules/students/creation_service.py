"""Tenant-admin student creation workflow."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.classes.repository import ClassRoomRepository
from app.modules.email_outbox.service import EmailOutboxService
from app.modules.student_academics.lifecycle_repository import (
    AcademicSessionLifecycleRepository,
)
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccessCodePurpose,
    StudentAccountStatus,
    StudentEnrollment,
    StudentEnrollmentOutcome,
    StudentProfileStatus,
)
from app.modules.students.repository import (
    StudentEnrollmentRepository,
    StudentRepository,
)
from app.modules.students.schemas import StudentCreate, StudentDetailResponse
from app.modules.students.service import (
    ParentInvitationService,
    StudentAccessCodeService,
    StudentService,
)
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.identifier_service import (
    TenantIdentifierKind,
    TenantIdentifierService,
)


class StudentCreationService:
    """Create students only after the school has completed onboarding."""

    @staticmethod
    async def create_student_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: StudentCreate,
    ) -> StudentDetailResponse:
        """Create student, enrollment, setup code, invitations, and email jobs."""

        tenant_id = StudentService._require_tenant_admin(actor)
        tenant = await TenantIdentifierService.require_completed_onboarding(
            db,
            tenant_id=tenant_id,
            lock=True,
        )

        classroom = await ClassRoomRepository.get_by_id(
            db,
            tenant_id,
            payload.class_id,
            lock=True,
        )
        if classroom is None or not classroom.is_active:
            raise NotFoundException("Class not found or inactive.")

        session = await AcademicSessionLifecycleRepository.get_current_open(
            db,
            tenant_id,
            lock=True,
        )
        if session is None:
            raise BadRequestException(
                "An open academic session is required before creating students."
            )

        admission_number = await TenantIdentifierService.generate_identifier(
            db,
            tenant=tenant,
            kind=TenantIdentifierKind.STUDENT,
        )
        student = Student(
            tenant_id=tenant_id,
            admission_number=admission_number,
            password_hash=None,
            first_name=payload.first_name,
            last_name=payload.last_name,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            state_of_origin=payload.state_of_origin,
            admission_date=date.today(),
            class_id=classroom.id,
            arm=classroom.arm,
            status=AcademicStatus.ACTIVE,
            account_status=StudentAccountStatus.ACTIVE,
            is_verified=True,
            is_active=True,
            password_reset_required=True,
            profile_status=(
                StudentProfileStatus.COMPLETE
                if payload.gender is not None
                else StudentProfileStatus.INCOMPLETE
            ),
        )

        try:
            student = await StudentRepository.add(db, student)
            await StudentEnrollmentRepository.add(
                db,
                StudentEnrollment(
                    tenant_id=tenant_id,
                    student_id=student.id,
                    class_id=classroom.id,
                    academic_session_id=session.id,
                    started_on=date.today(),
                    is_current=True,
                    outcome=StudentEnrollmentOutcome.ENROLLED,
                    reason="Initial admission",
                    changed_by_admin_id=actor.id,
                ),
            )
            await AuthIdentityService.create_for_actor(
                db,
                tenant_id=tenant_id,
                payload=AuthIdentityCreate(
                    identifier=student.admission_number,
                    identifier_type=IdentifierType.ADMISSION_NUMBER,
                    actor_type=ActorType.STUDENT,
                    actor_id=student.id,
                    is_active=True,
                ),
            )
            access_response = await StudentAccessCodeService._create_code(
                db,
                student=student,
                purpose=StudentAccessCodePurpose.INITIAL_SETUP,
                created_by_admin_id=actor.id,
                revoke_existing=False,
            )

            student_name = " ".join(
                part
                for part in [student.first_name, student.last_name]
                if part
            ) or "Student"

            for parent in payload.parents:
                normalized_email = str(parent.email).casefold()
                invitation = (
                    await ParentInvitationService._create_invitation_record(
                        db,
                        tenant_id=tenant_id,
                        student=student,
                        normalized_email=normalized_email,
                        relationship_type=parent.relationship_type,
                        created_by_admin_id=actor.id,
                    )
                )
                raw_token = getattr(invitation, "raw_token", None)
                if not raw_token:
                    raise RuntimeError(
                        "Parent invitation token was not generated."
                    )

                invite_link = (
                    f"{settings.FRONTEND_APP_URL.rstrip('/')}"
                    f"/parent-invitations/{raw_token}"
                )
                await EmailOutboxService.queue_parent_invitation_email(
                    db,
                    tenant_id=tenant_id,
                    email=normalized_email,
                    school_name=tenant.school_name,
                    student_name=student_name,
                    invite_link=invite_link,
                    metadata_json={
                        "source": "student_creation",
                        "student_id": str(student.id),
                        "invitation_id": str(invitation.id),
                        "relationship_type": parent.relationship_type.value,
                    },
                )

            await db.commit()
            await AuthIdentityService.invalidate_after_commit(db)
        except Exception:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)
            raise

        await db.refresh(student)
        detail = await StudentService._build_detail_response(db, student)
        return detail.model_copy(
            update={
                "setup_code": access_response.access_code,
                "access_code_expires_at": access_response.expires_at,
            }
        )
