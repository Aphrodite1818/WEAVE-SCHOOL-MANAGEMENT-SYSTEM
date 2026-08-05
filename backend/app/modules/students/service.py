"""Student creation, enrollment, access-code, linking, and lifecycle services."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import (
    hash_auth_secret,
    hash_password,
    verify_password,
)
from app.config.settings import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.auth.account_email_guard import AccountEmailGuard
from app.modules.auth.models import AuthSession, AuthSessionActorType
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.classes.repository import ClassRoomRepository
from app.modules.email_outbox.service import EmailOutboxService
from app.modules.parents.models import (
    ParentInvitation,
    ParentInvitationStatus,
    ParentMembership,
    ParentMembershipStatus,
)
from app.modules.parents.repository import (
    ParentInvitationRepository,
    ParentMembershipRepository,
)
from app.modules.student_academics.lifecycle_repository import (
    AcademicSessionLifecycleRepository,
)
from app.modules.student_academics.models import (
    AcademicSessionStatus,
    AcademicTermStatus,
    StudentSubjectResult,
)
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.students.models import (
    AcademicStatus,
    ParentLinkVerifiedByType,
    Student,
    StudentAccessCode,
    StudentAccessCodePurpose,
    StudentAccountStatus,
    StudentEnrollment,
    StudentEnrollmentOutcome,
    StudentParentLink,
    StudentParentLinkRequest,
    StudentParentLinkRequestStatus,
    StudentParentLinkStatus,
    StudentProfileStatus,
)
from app.modules.students.repository import (
    StudentAccessCodeRepository,
    StudentEnrollmentRepository,
    StudentParentLinkRepository,
    StudentParentLinkRequestRepository,
    StudentRepository,
)
from app.modules.students.schemas import (
    StudentAdminAccessCodeResponse,
    StudentAdminProfileUpdate,
    StudentChangePasswordRequest,
    StudentClassChangeRequest,
    StudentCreate,
    StudentDetailResponse,
    StudentEnrollmentDetailResponse,
    StudentHardDeleteEligibilityResponse,
    StudentLifecycleTransitionResponse,
    StudentOnboardingStatusResponse,
    StudentOnboardingUpdate,
    StudentParentLinkDetailResponse,
    StudentParentLinkRequestCreate,
    StudentParentLinkRequestDecision,
    StudentParentLinkRequestDetailResponse,
    StudentParentLinkRequestResponse,
    StudentParentLinkResponse,
    StudentParentLinkUpdateRequest,
    StudentResponse,
    StudentSelfUpdate,
)
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository
from app.tenant_management.identifier_service import (
    TenantIdentifierKind,
    TenantIdentifierService,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class StudentCreationWorkflowResult:
    """Result from the shared no-commit student creation workflow."""

    student: Student
    setup_code: str
    access_code_expires_at: datetime
    parent_invitation_count: int


class StudentService:
    """Student profile creation and safe profile access."""

    @staticmethod
    def _require_tenant_admin(actor: TenantAdmin) -> UUID:
        if not actor.tenant_id:
            raise ForbiddenException("Tenant admin is not attached to a tenant.")
        return actor.tenant_id

    @staticmethod
    def _require_student(actor: Student) -> UUID:
        if not actor.tenant_id:
            raise ForbiddenException("Student is not attached to a tenant.")
        return actor.tenant_id

    @staticmethod
    def _resolve_profile_status(student: Student) -> StudentProfileStatus:
        required = (
            student.first_name,
            student.last_name,
            student.gender,
        )
        return StudentProfileStatus.COMPLETE if all(required) else StudentProfileStatus.INCOMPLETE

    @staticmethod
    async def _generate_admission_number(
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> str:
        tenant = await TenantRepository.get_by_id(
            db,
            tenant_id,
            lock=True,
        )
        if tenant is None:
            raise NotFoundException("Tenant not found.")

        prefix = (
            (tenant.admission_number_prefix or tenant.slug.replace("-", "")[:6] or "STD")
            .strip()
            .upper()
        )
        year = date.today().year
        for _ in range(20):
            suffix = secrets.randbelow(900000) + 100000
            candidate = f"{prefix}/{year}/{suffix}"
            if not await StudentRepository.admission_number_exists(
                db,
                tenant_id,
                candidate,
            ):
                return candidate
        raise ConflictException("Could not allocate a unique admission number.")

    @staticmethod
    async def _build_detail_response(
        db: AsyncSession,
        student: Student,
    ) -> StudentDetailResponse:
        classroom = None
        if student.class_id:
            classroom = await ClassRoomRepository.get_by_id(
                db,
                student.tenant_id,
                student.class_id,
            )
        enrollment = await StudentEnrollmentRepository.get_current(
            db,
            student.tenant_id,
            student.id,
        )
        current_session = None
        if enrollment:
            current_session = await StudentAcademicRepository.get_academic_session_by_id(
                db,
                student.tenant_id,
                enrollment.academic_session_id,
            )
        if current_session is None:
            current_session = await StudentAcademicRepository.get_current_academic_session(
                db,
                student.tenant_id,
            )
        if current_session is None:
            sessions, _ = await StudentAcademicRepository.list_academic_sessions(
                db,
                student.tenant_id,
                limit=1,
                status=AcademicSessionStatus.CLOSING,
                is_current=True,
            )
            current_session = sessions[0] if sessions else None
        terms, _ = await StudentAcademicRepository.list_terms(
            db,
            student.tenant_id,
            limit=1,
            statuses={AcademicTermStatus.OPEN, AcademicTermStatus.CLOSING},
            is_current=True,
        )
        current_term = terms[0] if terms else None
        return StudentDetailResponse(
            **StudentResponse.model_validate(student).model_dump(),
            class_name=classroom.name if classroom else None,
            class_arm=classroom.arm if classroom else student.arm,
            current_enrollment_id=enrollment.id if enrollment else None,
            current_academic_session_id=current_session.id if current_session else None,
            current_academic_session_name=current_session.name if current_session else None,
            current_academic_term_id=current_term.id if current_term else None,
            current_academic_term_name=(
                current_term.name.value if current_term and current_term.name else None
            ),
        )

    @staticmethod
    async def create_student_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: StudentCreate,
    ) -> StudentDetailResponse:
        """Create student, enrollment, access code, and invitations atomically."""

        tenant_id = StudentService._require_tenant_admin(actor)
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

    @staticmethod
    async def _create_student_with_lifecycle(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        payload: StudentCreate,
        invitation_source: str,
    ) -> StudentCreationWorkflowResult:
        """Create a student lifecycle graph without committing.

        The caller owns the transaction. This keeps manual creation and bulk
        import on the same atomic workflow while preserving their commit rules.
        """

        tenant_id = StudentService._require_tenant_admin(actor)
        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=tenant_id,
            class_id=payload.class_id,
            lock=True,
        )
        if (
            classroom is None
            or not classroom.is_active
            or getattr(classroom, "archived_at", None) is not None
        ):
            raise NotFoundException("Class not found or inactive.")

        tenant = await TenantIdentifierService.require_completed_onboarding(
            db,
            tenant_id=tenant_id,
            lock=True,
        )

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
        today = date.today()
        student = Student(
            tenant_id=tenant_id,
            admission_number=admission_number,
            password_hash=None,
            first_name=payload.first_name,
            last_name=payload.last_name,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            passport_photo_url=None,
            admission_date=today,
            graduation_date=None,
            class_id=classroom.id,
            arm=classroom.arm,
            status=AcademicStatus.ACTIVE,
            account_status=StudentAccountStatus.ACTIVE,
            is_verified=True,
            is_active=True,
            password_reset_required=True,
            last_login_at=None,
            profile_status=StudentProfileStatus.INCOMPLETE,
            state_of_origin=payload.state_of_origin,
        )
        student.profile_status = StudentService._resolve_profile_status(student)

        created_student = await StudentRepository.add(db, student)
        await StudentEnrollmentRepository.add(
            db,
            StudentEnrollment(
                tenant_id=tenant_id,
                student_id=created_student.id,
                class_id=classroom.id,
                academic_session_id=session.id,
                started_on=today,
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
                identifier=created_student.admission_number,
                identifier_type=IdentifierType.ADMISSION_NUMBER,
                actor_type=ActorType.STUDENT,
                actor_id=created_student.id,
                is_active=True,
            ),
        )
        access_response = await StudentAccessCodeService._create_code(
            db,
            student=created_student,
            purpose=StudentAccessCodePurpose.INITIAL_SETUP,
            created_by_admin_id=actor.id,
            revoke_existing=False,
        )

        school_name = tenant.school_name if tenant is not None else "your school"
        student_name = (
            " ".join(
                part for part in [created_student.first_name, created_student.last_name] if part
            )
            or "Student"
        )

        for parent in payload.parents:
            normalized_email = str(parent.email).casefold()
            invitation = await ParentInvitationService._create_invitation_record(
                db,
                tenant_id=tenant_id,
                student=created_student,
                normalized_email=normalized_email,
                relationship_type=parent.relationship_type,
                created_by_admin_id=actor.id,
            )
            raw_token = getattr(invitation, "raw_token", None)
            if not raw_token:
                raise RuntimeError("Parent invitation token was not generated.")

            await EmailOutboxService.queue_parent_invitation_email(
                db,
                tenant_id=tenant_id,
                email=normalized_email,
                school_name=school_name,
                student_name=student_name,
                invite_link=(
                    f"{settings.FRONTEND_APP_URL.rstrip('/')}/parent-invitations/{raw_token}"
                ),
                admission_number=created_student.admission_number,
                metadata_json={
                    "source": invitation_source,
                    "actor_type": "parent",
                    "student_id": str(created_student.id),
                    "invitation_id": str(invitation.id),
                    "relationship_type": parent.relationship_type.value,
                },
            )

        return StudentCreationWorkflowResult(
            student=created_student,
            setup_code=access_response.access_code,
            access_code_expires_at=access_response.expires_at,
            parent_invitation_count=len(payload.parents),
        )

    @staticmethod
    async def get_student_profile(
        db: AsyncSession,
        actor: TenantAdmin | Student | ParentMembership | object,
        student_id: UUID,
    ) -> StudentDetailResponse:
        tenant_id = getattr(actor, "tenant_id", None)
        if tenant_id is None:
            raise ForbiddenException("Actor has no tenant context.")

        if isinstance(actor, ParentMembership):
            links = await StudentParentLinkRepository.list_for_membership(
                db,
                tenant_id,
                actor.id,
                statuses=[
                    StudentParentLinkStatus.ACTIVE,
                    StudentParentLinkStatus.READ_ONLY,
                    StudentParentLinkStatus.ALUMNI_READ_ONLY,
                ],
            )
            if not any(link.student_id == student_id for link in links):
                raise ForbiddenException("This parent membership cannot access the student.")

        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        return await StudentService._build_detail_response(db, student)

    @staticmethod
    async def get_my_student_profile(
        db: AsyncSession,
        actor: Student,
    ) -> StudentDetailResponse:
        StudentService._require_student(actor)
        student = await StudentRepository.get_by_id(
            db,
            actor.tenant_id,
            actor.id,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        return await StudentService._build_detail_response(db, student)

    @staticmethod
    async def list_students(
        db: AsyncSession,
        actor: TenantAdmin | ParentMembership | object,
        *,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        class_id: UUID | None = None,
        status: AcademicStatus | None = None,
    ) -> tuple[list[StudentDetailResponse], int]:
        tenant_id = getattr(actor, "tenant_id", None)
        if tenant_id is None:
            raise ForbiddenException("Actor has no tenant context.")

        students, total = await StudentRepository.list_for_tenant(
            db,
            tenant_id,
            search=search,
            class_id=class_id,
            status=status,
            offset=skip,
            limit=min(limit, 100),
        )
        if isinstance(actor, ParentMembership):
            links = await StudentParentLinkRepository.list_for_membership(
                db,
                tenant_id,
                actor.id,
                statuses=[
                    StudentParentLinkStatus.ACTIVE,
                    StudentParentLinkStatus.READ_ONLY,
                    StudentParentLinkStatus.ALUMNI_READ_ONLY,
                ],
            )
            allowed = {link.student_id for link in links}
            students = [student for student in students if student.id in allowed]
            total = len(students)

        return [
            await StudentService._build_detail_response(db, student) for student in students
        ], total

    @staticmethod
    async def update_student_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        student_id: UUID,
        payload: StudentAdminProfileUpdate,
    ) -> StudentDetailResponse:
        tenant_id = StudentService._require_tenant_admin(actor)
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            lock=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")

        for field, value in payload.model_dump(
            exclude_unset=True,
            exclude_none=True,
        ).items():
            setattr(student, field, value)
        student.profile_status = StudentService._resolve_profile_status(student)
        await StudentRepository.save(db, student)
        await db.commit()
        await db.refresh(student)
        return await StudentService._build_detail_response(db, student)

    @staticmethod
    async def update_my_student_profile(
        db: AsyncSession,
        actor: Student,
        payload: StudentSelfUpdate | StudentOnboardingUpdate,
    ) -> StudentDetailResponse:
        StudentService._require_student(actor)
        student = await StudentRepository.get_by_id(
            db,
            actor.tenant_id,
            actor.id,
            lock=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")

        for field, value in payload.model_dump(
            exclude_unset=True,
            exclude_none=True,
        ).items():
            setattr(student, field, value)
        student.profile_status = StudentService._resolve_profile_status(student)
        await StudentRepository.save(db, student)
        await db.commit()
        await db.refresh(student)
        return await StudentService._build_detail_response(db, student)

    @staticmethod
    async def get_my_onboarding_status(
        db: AsyncSession,
        actor: Student,
    ) -> StudentOnboardingStatusResponse:
        student = await StudentRepository.get_by_id(
            db,
            actor.tenant_id,
            actor.id,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        return StudentOnboardingStatusResponse(
            actor_type="student",
            student_id=student.id,
            onboarding_required=(student.profile_status != StudentProfileStatus.COMPLETE),
            profile_status=student.profile_status,
            completion_target="student",
            required_fields=["first_name", "last_name", "gender"],
            current_values={
                "admission_number": student.admission_number,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "gender": student.gender,
            },
        )

    @staticmethod
    async def admin_reset_student_access_code(
        db: AsyncSession,
        actor: TenantAdmin,
        student_id: UUID,
    ) -> StudentAdminAccessCodeResponse:
        return await StudentAccessCodeService.generate_for_admin(
            db,
            actor=actor,
            student_id=student_id,
            purpose=StudentAccessCodePurpose.PASSWORD_RESET,
        )


class StudentAccessCodeService:
    @staticmethod
    def _generate_code() -> str:
        length = settings.STUDENT_ACCESS_CODE_LENGTH
        return "".join(secrets.choice("0123456789") for _ in range(length))

    @staticmethod
    async def _create_code(
        db: AsyncSession,
        *,
        student: Student,
        purpose: StudentAccessCodePurpose,
        created_by_admin_id: UUID | None,
        revoke_existing: bool = True,
    ) -> StudentAdminAccessCodeResponse:
        if revoke_existing:
            await StudentAccessCodeRepository.mark_all_codes_used(
                db,
                student.tenant_id,
                student.id,
            )
        raw_code = StudentAccessCodeService._generate_code()
        expires_at = _utc_now() + timedelta(hours=settings.STUDENT_ACCESS_CODE_EXPIRY_HOURS)
        await StudentAccessCodeRepository.add(
            db,
            StudentAccessCode(
                tenant_id=student.tenant_id,
                student_id=student.id,
                code_digest=hash_auth_secret(raw_code),
                purpose=purpose,
                expires_at=expires_at,
                created_by_admin_id=created_by_admin_id,
            ),
        )
        return StudentAdminAccessCodeResponse(
            student_id=student.id,
            admission_number=student.admission_number,
            full_name=" ".join(part for part in [student.first_name, student.last_name] if part)
            or None,
            purpose=purpose,
            access_code=raw_code,
            expires_at=expires_at,
        )

    @staticmethod
    async def generate_for_admin(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        purpose: StudentAccessCodePurpose,
    ) -> StudentAdminAccessCodeResponse:
        tenant_id = StudentService._require_tenant_admin(actor)
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            lock=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        if (
            student.status
            in {
                AcademicStatus.WITHDRAWN,
                AcademicStatus.EXPELLED,
                AcademicStatus.GRADUATED,
            }
            or student.is_archived
        ):
            raise BadRequestException("Access codes cannot be generated for inactive students.")

        response = await StudentAccessCodeService._create_code(
            db,
            student=student,
            purpose=purpose,
            created_by_admin_id=actor.id,
        )
        if purpose == StudentAccessCodePurpose.PASSWORD_RESET:
            student.password_hash = None
            await db.execute(
                update(AuthSession)
                .where(
                    AuthSession.actor_type == AuthSessionActorType.STUDENT,
                    AuthSession.actor_id == student.id,
                    AuthSession.tenant_id == student.tenant_id,
                    AuthSession.revoked_at.is_(None),
                )
                .values(
                    revoked_at=_utc_now(),
                    revoked_reason="student_password_reset",
                )
            )
        student.password_reset_required = True
        await StudentRepository.save(db, student)
        await db.commit()
        return response

    @staticmethod
    async def change_password(
        db: AsyncSession,
        *,
        actor: Student,
        payload: StudentChangePasswordRequest,
    ) -> StudentDetailResponse:
        student = await StudentRepository.get_by_id(
            db,
            actor.tenant_id,
            actor.id,
            lock=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")

        code = await StudentAccessCodeRepository.get_by_digest(
            db,
            student.tenant_id,
            student.id,
            hash_auth_secret(payload.access_code),
            lock=True,
            require_active=True,
        )
        if code is None:
            raise BadRequestException("Access code is invalid or expired.")
        if student.password_hash and verify_password(payload.new_password, student.password_hash):
            raise BadRequestException("New password must differ from the current password.")

        student.password_hash = hash_password(payload.new_password)
        student.password_reset_required = False
        student.account_status = StudentAccountStatus.ACTIVE
        student.is_active = True
        code.is_used = True
        code.used_at = _utc_now()
        await StudentAccessCodeRepository.save(db, code)
        await StudentRepository.save(db, student)
        await db.commit()
        await db.refresh(student)
        return await StudentService._build_detail_response(db, student)


class ParentInvitationService:
    @staticmethod
    def _generate_token() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    async def _create_invitation_record(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student: Student,
        normalized_email: str,
        relationship_type,
        created_by_admin_id: UUID,
    ) -> ParentInvitation:
        normalized_email = await AccountEmailGuard.ensure_available_for_invitation_role(
            db=db,
            email=normalized_email,
            invited_actor_type=ActorType.PARENT_ACCOUNT,
        )
        existing = await ParentInvitationRepository.get_pending_for_student_email(
            db,
            tenant_id,
            student.id,
            normalized_email,
            lock=True,
        )
        if existing is not None:
            return existing

        raw_token = ParentInvitationService._generate_token()
        invitation = ParentInvitation(
            tenant_id=tenant_id,
            student_id=student.id,
            invited_email=normalized_email,
            relationship_type=relationship_type,
            admission_number_snapshot=student.admission_number,
            token_digest=hash_auth_secret(raw_token),
            status=ParentInvitationStatus.PENDING,
            expires_at=_utc_now() + timedelta(days=7),
            created_by_admin_id=created_by_admin_id,
        )
        invitation = await ParentInvitationRepository.add(db, invitation)
        invitation.raw_token = raw_token
        return invitation


class StudentEnrollmentService:
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
            output.append(
                StudentEnrollmentDetailResponse(
                    **StudentEnrollmentDetailResponse.model_validate(row).model_dump(
                        exclude={
                            "class_name",
                            "class_arm",
                            "academic_session_name",
                        }
                    ),
                    class_name=classroom.name if classroom else None,
                    class_arm=classroom.arm if classroom else None,
                    academic_session_name=(session.name if session else None),
                )
            )
        return output

    @staticmethod
    async def change_class(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        payload: StudentClassChangeRequest,
    ) -> StudentDetailResponse:
        tenant_id = StudentService._require_tenant_admin(actor)
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            lock=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        if student.status not in {
            AcademicStatus.ACTIVE,
            AcademicStatus.SUSPENDED,
        }:
            raise BadRequestException("Only active or suspended students can change class.")

        target_class = await ClassRoomRepository.get_by_id(
            db,
            tenant_id,
            payload.target_class_id,
            lock=True,
        )
        if (
            target_class is None
            or not target_class.is_active
            or target_class.archived_at is not None
        ):
            raise NotFoundException("Target class not found.")
        session = await AcademicSessionLifecycleRepository.get_by_id(
            db,
            tenant_id,
            payload.academic_session_id,
            lock=True,
        )
        if (
            session is None
            or not session.is_current
            or session.status != AcademicSessionStatus.OPEN
        ):
            raise NotFoundException("Academic session not found.")

        current = await StudentEnrollmentRepository.get_current(
            db,
            tenant_id,
            student.id,
            lock=True,
        )
        if current is None:
            raise ConflictException("Student has no current enrollment to close.")
        if current.class_id == target_class.id:
            raise ConflictException("Student is already in the target class.")

        current.is_current = False
        current.ended_on = payload.effective_date
        current.outcome = StudentEnrollmentOutcome(payload.outcome)
        current.reason = payload.reason
        current.changed_by_admin_id = actor.id
        await StudentEnrollmentRepository.save(db, current)

        await StudentEnrollmentRepository.add(
            db,
            StudentEnrollment(
                tenant_id=tenant_id,
                student_id=student.id,
                class_id=target_class.id,
                academic_session_id=session.id,
                started_on=payload.effective_date,
                is_current=True,
                outcome=StudentEnrollmentOutcome(payload.outcome),
                reason=payload.reason,
                changed_by_admin_id=actor.id,
            ),
        )
        student.class_id = target_class.id
        student.arm = target_class.arm
        await StudentRepository.save(db, student)
        await db.commit()
        await db.refresh(student)
        return await StudentService._build_detail_response(db, student)


class StudentLifecycleService:
    @staticmethod
    async def _revoke_student_access(
        db: AsyncSession,
        student: Student,
        *,
        reason: str,
    ) -> tuple[bool, int]:
        now = _utc_now()
        result = await db.execute(
            update(AuthSession)
            .where(
                AuthSession.actor_type == AuthSessionActorType.STUDENT,
                AuthSession.actor_id == student.id,
                AuthSession.tenant_id == student.tenant_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(
                revoked_at=now,
                revoked_reason=reason[:100],
            )
        )
        code_count = await StudentAccessCodeRepository.mark_all_codes_used(
            db,
            student.tenant_id,
            student.id,
        )
        return bool(result.rowcount), code_count

    @staticmethod
    async def _recalculate_parent_membership(
        db: AsyncSession,
        membership: ParentMembership,
    ) -> bool:
        counts = await ParentMembershipRepository.get_link_status_counts(
            db,
            membership.tenant_id,
            membership.id,
        )
        now = _utc_now()
        if counts.get(StudentParentLinkStatus.ACTIVE, 0) > 0:
            target = ParentMembershipStatus.ACTIVE
        elif (
            counts.get(StudentParentLinkStatus.READ_ONLY, 0) > 0
            or counts.get(
                StudentParentLinkStatus.ALUMNI_READ_ONLY,
                0,
            )
            > 0
        ):
            target = ParentMembershipStatus.READ_ONLY
        else:
            target = ParentMembershipStatus.INACTIVE

        changed = membership.status != target
        membership.status = target
        if target == ParentMembershipStatus.INACTIVE:
            membership.ended_at = membership.ended_at or now
            membership.end_reason = membership.end_reason or "No usable student links remain."
        else:
            membership.ended_at = None
            membership.end_reason = None
        await ParentMembershipRepository.save(db, membership)
        return changed

    @staticmethod
    async def _transition(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        target_status: AcademicStatus,
        reason: str,
        effective_date: date,
        promotion_hold: bool | None = None,
    ) -> StudentLifecycleTransitionResponse:
        tenant_id = StudentService._require_tenant_admin(actor)
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            lock=True,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")

        previous_status = student.status
        if previous_status == target_status:
            raise ConflictException(f"Student is already {target_status.value}.")

        now = _utc_now()
        terminal = target_status in {
            AcademicStatus.WITHDRAWN,
            AcademicStatus.EXPELLED,
            AcademicStatus.GRADUATED,
        }
        if target_status == AcademicStatus.SUSPENDED:
            if previous_status != AcademicStatus.ACTIVE:
                raise BadRequestException("Only active students can be suspended.")
            student.status = target_status
            student.promotion_hold = promotion_hold if promotion_hold is not None else True
            student.is_active = False
            student.account_status = StudentAccountStatus.INACTIVE
        elif target_status == AcademicStatus.ACTIVE:
            if previous_status != AcademicStatus.SUSPENDED:
                raise BadRequestException(
                    "Only suspended students can be reinstated through this endpoint."
                )
            student.status = AcademicStatus.ACTIVE
            student.promotion_hold = False
            student.is_active = True
            student.account_status = StudentAccountStatus.ACTIVE
            student.graduation_date = None
            await AuthIdentityService.ensure_for_actor(
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
        elif terminal:
            current = await StudentEnrollmentRepository.get_current(
                db,
                tenant_id,
                student.id,
                lock=True,
            )
            if current is not None:
                current.is_current = False
                current.ended_on = effective_date
                current.outcome = StudentEnrollmentOutcome(target_status.value)
                current.reason = reason
                current.changed_by_admin_id = actor.id
                await StudentEnrollmentRepository.save(db, current)

            student.status = target_status
            student.class_id = None
            student.arm = None
            student.promotion_hold = True
            student.is_active = False
            student.account_status = StudentAccountStatus.INACTIVE
            if target_status == AcademicStatus.GRADUATED:
                student.graduation_date = effective_date
        else:
            raise BadRequestException("Unsupported student lifecycle transition.")

        await StudentRepository.save(db, student)
        if target_status == AcademicStatus.ACTIVE:
            session_revoked = False
            codes_revoked = 0
        else:
            session_revoked, codes_revoked = await StudentLifecycleService._revoke_student_access(
                db,
                student,
                reason=target_status.value,
            )

        links = await StudentParentLinkRepository.list_for_student(
            db,
            tenant_id,
            student.id,
            statuses=[
                StudentParentLinkStatus.ACTIVE,
                StudentParentLinkStatus.READ_ONLY,
                StudentParentLinkStatus.ALUMNI_READ_ONLY,
            ],
            lock=True,
        )
        affected_links = 0
        recalculated_memberships: set[UUID] = set()
        for link in links:
            if target_status == AcademicStatus.WITHDRAWN:
                link.status = StudentParentLinkStatus.READ_ONLY
            elif target_status == AcademicStatus.GRADUATED:
                link.status = StudentParentLinkStatus.ALUMNI_READ_ONLY
            elif target_status == AcademicStatus.EXPELLED:
                link.status = StudentParentLinkStatus.ENDED
                link.ended_at = now
                link.end_reason = reason
            elif target_status == AcademicStatus.ACTIVE:
                link.status = StudentParentLinkStatus.ACTIVE
                link.ended_at = None
                link.end_reason = None
            else:
                continue
            await StudentParentLinkRepository.save(db, link)
            affected_links += 1
            recalculated_memberships.add(link.parent_membership_id)

        recalculation_count = 0
        for membership_id in recalculated_memberships:
            membership = await ParentMembershipRepository.get_by_id(
                db,
                membership_id,
                tenant_id=tenant_id,
                lock=True,
            )
            if membership is not None:
                await StudentLifecycleService._recalculate_parent_membership(
                    db,
                    membership,
                )
                recalculation_count += 1

        await db.commit()
        await AuthIdentityService.invalidate_after_commit(db)
        await db.refresh(student)
        return StudentLifecycleTransitionResponse(
            student=await StudentService._build_detail_response(db, student),
            previous_status=previous_status,
            new_status=student.status,
            session_revoked=session_revoked,
            access_codes_revoked=codes_revoked,
            affected_parent_links=affected_links,
            membership_recalculations=recalculation_count,
        )

    @staticmethod
    async def suspend(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
        promotion_hold: bool = True,
    ) -> StudentLifecycleTransitionResponse:
        return await StudentLifecycleService._transition(
            db,
            actor=actor,
            student_id=student_id,
            target_status=AcademicStatus.SUSPENDED,
            reason=reason,
            effective_date=date.today(),
            promotion_hold=promotion_hold,
        )

    @staticmethod
    async def reinstate(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
    ) -> StudentLifecycleTransitionResponse:
        return await StudentLifecycleService._transition(
            db,
            actor=actor,
            student_id=student_id,
            target_status=AcademicStatus.ACTIVE,
            reason=reason,
            effective_date=date.today(),
        )

    @staticmethod
    async def reinstate_expelled(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        target_class_id: UUID,
        academic_session_id: UUID,
        effective_date: date,
        reason: str,
    ) -> StudentLifecycleTransitionResponse:
        tenant_id = StudentService._require_tenant_admin(actor)
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            lock=True,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        if student.is_archived:
            raise ConflictException("Restore the archived student before reinstatement.")
        if student.status != AcademicStatus.EXPELLED:
            raise BadRequestException("Only expelled students use this reinstatement endpoint.")

        classroom = await ClassRoomRepository.get_by_id(
            db,
            tenant_id,
            target_class_id,
            lock=True,
        )
        if classroom is None or not classroom.is_active or classroom.archived_at is not None:
            raise NotFoundException("Target class not found.")
        session = await AcademicSessionLifecycleRepository.get_by_id(
            db,
            tenant_id,
            academic_session_id,
            lock=True,
        )
        if session is None or session.status != AcademicSessionStatus.OPEN:
            raise NotFoundException("Academic session not found or not open.")

        previous_status = student.status
        await StudentEnrollmentRepository.add(
            db,
            StudentEnrollment(
                tenant_id=tenant_id,
                student_id=student.id,
                class_id=classroom.id,
                academic_session_id=session.id,
                started_on=effective_date,
                is_current=True,
                outcome=StudentEnrollmentOutcome.RECLASSIFIED,
                reason=reason,
                changed_by_admin_id=actor.id,
            ),
        )
        student.status = AcademicStatus.ACTIVE
        student.class_id = classroom.id
        student.arm = classroom.arm
        student.promotion_hold = False
        student.is_active = True
        student.account_status = StudentAccountStatus.ACTIVE
        student.graduation_date = None
        await StudentRepository.save(db, student)
        await AuthIdentityService.ensure_for_actor(
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

        links = await StudentParentLinkRepository.list_for_student(
            db,
            tenant_id,
            student.id,
            statuses=[StudentParentLinkStatus.ENDED],
            lock=True,
        )
        membership_ids: set[UUID] = set()
        for link in links:
            link.status = StudentParentLinkStatus.ACTIVE
            link.ended_at = None
            link.end_reason = None
            await StudentParentLinkRepository.save(db, link)
            membership_ids.add(link.parent_membership_id)

        recalculations = 0
        for membership_id in membership_ids:
            membership = await ParentMembershipRepository.get_by_id(
                db,
                membership_id,
                tenant_id=tenant_id,
                lock=True,
            )
            if membership is not None:
                await StudentLifecycleService._recalculate_parent_membership(
                    db,
                    membership,
                )
                recalculations += 1

        await db.commit()
        await AuthIdentityService.invalidate_after_commit(db)
        await db.refresh(student)
        return StudentLifecycleTransitionResponse(
            student=await StudentService._build_detail_response(db, student),
            previous_status=previous_status,
            new_status=student.status,
            session_revoked=False,
            access_codes_revoked=0,
            affected_parent_links=len(links),
            membership_recalculations=recalculations,
        )

    @staticmethod
    async def withdraw(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
        effective_date: date,
    ) -> StudentLifecycleTransitionResponse:
        return await StudentLifecycleService._transition(
            db,
            actor=actor,
            student_id=student_id,
            target_status=AcademicStatus.WITHDRAWN,
            reason=reason,
            effective_date=effective_date,
        )

    @staticmethod
    async def expel(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
        effective_date: date,
    ) -> StudentLifecycleTransitionResponse:
        return await StudentLifecycleService._transition(
            db,
            actor=actor,
            student_id=student_id,
            target_status=AcademicStatus.EXPELLED,
            reason=reason,
            effective_date=effective_date,
        )

    @staticmethod
    async def graduate(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
        graduation_date: date,
    ) -> StudentLifecycleTransitionResponse:
        return await StudentLifecycleService._transition(
            db,
            actor=actor,
            student_id=student_id,
            target_status=AcademicStatus.GRADUATED,
            reason=reason,
            effective_date=graduation_date,
        )

    @staticmethod
    async def archive(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
    ) -> StudentResponse:
        tenant_id = StudentService._require_tenant_admin(actor)
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            lock=True,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        if student.is_archived:
            raise ConflictException("Student is already archived.")

        student.is_archived = True
        student.archived_at = _utc_now()
        student.archived_by_admin_id = actor.id
        student.archive_reason = reason
        student.is_active = False
        student.account_status = StudentAccountStatus.INACTIVE
        await StudentRepository.save(db, student)
        await StudentLifecycleService._revoke_student_access(
            db,
            student,
            reason="archived",
        )
        await AuthIdentityService.deactivate_for_actor(
            db,
            actor_type=ActorType.STUDENT,
            actor_id=student.id,
        )
        await db.commit()
        await AuthIdentityService.invalidate_after_commit(db)
        await db.refresh(student)
        return await StudentService._build_detail_response(db, student)

    @staticmethod
    async def restore(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
    ) -> StudentResponse:
        tenant_id = StudentService._require_tenant_admin(actor)
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            lock=True,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        if not student.is_archived:
            raise ConflictException("Student is not archived.")

        student.is_archived = False
        student.archived_at = None
        student.archived_by_admin_id = None
        student.archive_reason = None
        if student.status == AcademicStatus.ACTIVE:
            student.is_active = True
            student.account_status = StudentAccountStatus.ACTIVE
            await AuthIdentityService.ensure_for_actor(
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
        await StudentRepository.save(db, student)
        await db.commit()
        await AuthIdentityService.invalidate_after_commit(db)
        await db.refresh(student)
        return await StudentService._build_detail_response(db, student)

    @staticmethod
    async def hard_delete_eligibility(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
    ) -> StudentHardDeleteEligibilityResponse:
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")

        blockers: list[str] = []
        if (
            await StudentParentLinkRepository.count_for_student(
                db,
                tenant_id,
                student_id,
            )
            > 0
        ):
            blockers.append("parent_links")

        result_count = (
            await db.execute(
                select(func.count())
                .select_from(StudentSubjectResult)
                .where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.student_id == student_id,
                )
            )
        ).scalar_one()
        if result_count:
            blockers.append("academic_results")

        return StudentHardDeleteEligibilityResponse(
            student_id=student.id,
            eligible=not blockers,
            blocking_dependencies=blockers,
            recommendation=("hard_delete" if not blockers else "archive"),
        )

    @staticmethod
    async def hard_delete(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
    ) -> None:
        tenant_id = StudentService._require_tenant_admin(actor)
        eligibility = await StudentLifecycleService.hard_delete_eligibility(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
        )
        if not eligibility.eligible:
            raise ConflictException("Student has historical dependencies and must be archived.")

        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            lock=True,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        await db.execute(
            delete(StudentParentLinkRequest).where(
                StudentParentLinkRequest.tenant_id == tenant_id,
                StudentParentLinkRequest.student_id == student_id,
            )
        )
        await db.execute(
            delete(ParentInvitation).where(
                ParentInvitation.tenant_id == tenant_id,
                ParentInvitation.student_id == student_id,
            )
        )
        await db.execute(
            delete(StudentAccessCode).where(
                StudentAccessCode.tenant_id == tenant_id,
                StudentAccessCode.student_id == student_id,
            )
        )
        await db.execute(
            delete(StudentEnrollment).where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.student_id == student_id,
            )
        )
        await AuthIdentityService.deactivate_for_actor(
            db,
            actor_type=ActorType.STUDENT,
            actor_id=student.id,
        )
        await StudentRepository.hard_delete(db, student)
        await db.commit()
        await AuthIdentityService.invalidate_after_commit(db)


class StudentParentLinkService:
    @staticmethod
    async def _detail(
        link: StudentParentLink,
    ) -> StudentParentLinkDetailResponse:
        membership = link.parent_membership
        account = membership.parent_account
        return StudentParentLinkDetailResponse(
            **StudentParentLinkResponse.model_validate(link).model_dump(),
            parent_account_id=account.id,
            parent_first_name=account.first_name,
            parent_last_name=account.last_name,
            parent_email=account.email,
            membership_status=membership.status,
        )

    @staticmethod
    async def list_my_parent_links(
        db: AsyncSession,
        actor: Student,
    ) -> tuple[list[StudentParentLinkDetailResponse], int]:
        links = await StudentParentLinkRepository.list_for_student(
            db,
            actor.tenant_id,
            actor.id,
        )
        return [await StudentParentLinkService._detail(link) for link in links], len(links)

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        link_id: UUID,
        payload: StudentParentLinkUpdateRequest,
    ) -> StudentParentLinkResponse:
        link = await StudentParentLinkRepository.get_by_id(
            db,
            actor.tenant_id,
            link_id,
            lock=True,
        )
        if link is None:
            raise NotFoundException("Parent link not found.")
        for field, value in payload.model_dump(
            exclude_unset=True,
            exclude_none=True,
        ).items():
            setattr(link, field, value)
        await StudentParentLinkRepository.save(db, link)
        await db.commit()
        await db.refresh(link)
        return StudentParentLinkResponse.model_validate(link)


class StudentParentLinkRequestService:
    @staticmethod
    async def create_request(
        db: AsyncSession,
        actor: ParentMembership,
        payload: StudentParentLinkRequestCreate,
    ) -> StudentParentLinkRequestDetailResponse:
        invitation = await ParentInvitationRepository.get_by_token_digest(
            db,
            hash_auth_secret(payload.invitation_token),
            lock=True,
        )
        if invitation is None:
            raise NotFoundException("Invitation not found.")
        if invitation.status != ParentInvitationStatus.PENDING:
            raise ConflictException("Invitation is no longer pending.")
        if invitation.expires_at <= _utc_now():
            invitation.status = ParentInvitationStatus.EXPIRED
            await ParentInvitationRepository.save(db, invitation)
            raise BadRequestException("Invitation has expired.")
        if actor.tenant_id != invitation.tenant_id:
            raise ForbiddenException("Select the invited school before continuing.")
        if actor.email.casefold() != invitation.invited_email.casefold():
            raise ForbiddenException("Invitation belongs to a different email.")
        if payload.admission_number.strip().upper() != invitation.admission_number_snapshot.upper():
            raise BadRequestException("Admission number does not match.")

        existing = await StudentParentLinkRequestRepository.get_by_invitation(
            db,
            invitation.id,
            lock=True,
        )
        if existing is not None:
            return await StudentParentLinkRequestService._detail(
                db,
                existing,
            )

        request = StudentParentLinkRequest(
            tenant_id=invitation.tenant_id,
            invitation_id=invitation.id,
            student_id=invitation.student_id,
            parent_account_id=actor.parent_account_id,
            parent_membership_id=actor.id,
            admission_number_snapshot=invitation.admission_number_snapshot,
            relationship_type=invitation.relationship_type,
            status=StudentParentLinkRequestStatus.PENDING,
            requested_at=_utc_now(),
        )
        request = await StudentParentLinkRequestRepository.add(db, request)
        await db.commit()
        return await StudentParentLinkRequestService._detail(db, request)

    @staticmethod
    async def _detail(
        db: AsyncSession,
        request: StudentParentLinkRequest,
    ) -> StudentParentLinkRequestDetailResponse:
        student = await StudentRepository.get_by_id(
            db,
            request.tenant_id,
            request.student_id,
            include_archived=True,
        )
        membership = (
            await ParentMembershipRepository.get_by_id(
                db,
                request.parent_membership_id,
                tenant_id=request.tenant_id,
            )
            if request.parent_membership_id
            else None
        )
        account = membership.parent_account if membership else None
        base = StudentParentLinkRequestResponse.model_validate(request).model_dump()
        return StudentParentLinkRequestDetailResponse(
            **base,
            parent_email=(account.email if account else "unknown@example.com"),
            parent_first_name=(account.first_name if account else None),
            parent_last_name=(account.last_name if account else None),
            student_name=(
                " ".join(part for part in [student.first_name, student.last_name] if part)
                if student
                else None
            ),
        )

    @staticmethod
    async def list_student_requests(
        db: AsyncSession,
        actor: Student,
    ) -> tuple[list[StudentParentLinkRequestDetailResponse], int]:
        rows = await StudentParentLinkRequestRepository.list_pending_for_student(
            db,
            actor.tenant_id,
            actor.id,
        )
        return [await StudentParentLinkRequestService._detail(db, row) for row in rows], len(rows)

    @staticmethod
    async def list_parent_requests(
        db: AsyncSession,
        actor: ParentMembership,
    ) -> tuple[list[StudentParentLinkRequestDetailResponse], int]:
        rows, _ = await StudentParentLinkRequestRepository.list_pending_for_tenant(
            db,
            actor.tenant_id,
            offset=0,
            limit=100,
        )
        rows = [row for row in rows if row.parent_membership_id == actor.id]
        return [await StudentParentLinkRequestService._detail(db, row) for row in rows], len(rows)

    @staticmethod
    async def respond_to_request(
        db: AsyncSession,
        actor: Student | TenantAdmin,
        request_id: UUID,
        payload: StudentParentLinkRequestDecision,
    ) -> StudentParentLinkRequestDetailResponse:
        request = await StudentParentLinkRequestRepository.get_by_id(
            db,
            actor.tenant_id,
            request_id,
            lock=True,
        )
        if request is None:
            raise NotFoundException("Parent link request not found.")
        if request.status != StudentParentLinkRequestStatus.PENDING:
            raise ConflictException("Request has already been decided.")
        if isinstance(actor, Student) and request.student_id != actor.id:
            raise ForbiddenException("Student cannot decide another student's request.")

        now = _utc_now()
        responder_type = (
            ParentLinkVerifiedByType.STUDENT
            if isinstance(actor, Student)
            else ParentLinkVerifiedByType.TENANT_ADMIN
        )
        if payload.action == "reject":
            request.status = StudentParentLinkRequestStatus.REJECTED
            request.responded_at = now
            request.responded_by_type = responder_type
            request.responded_by_id = actor.id
            request.rejection_reason = payload.reason
        else:
            membership = await ParentMembershipRepository.get_by_id(
                db,
                request.parent_membership_id,
                tenant_id=request.tenant_id,
                lock=True,
            )
            if membership is None:
                raise ConflictException("Parent membership no longer exists.")
            existing_link = await StudentParentLinkRepository.get_by_student_and_membership(
                db,
                request.tenant_id,
                request.student_id,
                membership.id,
                lock=True,
            )
            request.status = StudentParentLinkRequestStatus.APPROVED
            request.responded_at = now
            request.responded_by_type = responder_type
            request.responded_by_id = actor.id
            request.rejection_reason = None
            if existing_link is None:
                await StudentParentLinkRepository.add(
                    db,
                    StudentParentLink(
                        tenant_id=request.tenant_id,
                        student_id=request.student_id,
                        parent_membership_id=membership.id,
                        relationship_type=request.relationship_type,
                        status=StudentParentLinkStatus.ACTIVE,
                        verified_at=now,
                        verified_by_type=responder_type,
                        verified_by_id=actor.id,
                    ),
                )
            else:
                existing_link.status = StudentParentLinkStatus.ACTIVE
                existing_link.ended_at = None
                existing_link.end_reason = None
                await StudentParentLinkRepository.save(db, existing_link)
            membership.status = ParentMembershipStatus.ACTIVE
            membership.ended_at = None
            membership.end_reason = None
            await ParentMembershipRepository.save(db, membership)

            invitation = await ParentInvitationRepository.get_by_id(
                db,
                request.tenant_id,
                request.invitation_id,
                lock=True,
            )
            if invitation is not None:
                invitation.status = ParentInvitationStatus.ACCEPTED
                invitation.accepted_at = now
                invitation.accepted_by_parent_account_id = request.parent_account_id
                await ParentInvitationRepository.save(db, invitation)

        await StudentParentLinkRequestRepository.save(db, request)
        await db.commit()
        return await StudentParentLinkRequestService._detail(db, request)
