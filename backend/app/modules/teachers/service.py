# ====================================== #
#              service.py                #
# ====================================== #

"""Teacher service layer."""

import secrets
from fastapi import BackgroundTasks
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_password
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.core.utils.normalization import normalize_staff_id
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.subjects.models import Subject
from app.modules.subjects.repository import SubjectRepository
from app.modules.auth.service import UserInviteService
from app.modules.teachers.models import Teacher, TeacherAccountStatus, TeacherStatus
from app.modules.teachers.repository import TeacherRepository
from app.modules.teachers.schemas import (
    TeacherCreate,
    TeacherOnboardingStatusResponse,
    TeacherOnboardingUpdate,
    TeacherSelfUpdate,
    TeacherUpdate,
)
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository


class TeacherService:
    """Business logic for teacher actors."""

    @staticmethod
    def _normalize_email(email: str) -> str:
        """Normalize teacher email."""

        return email.strip().lower()

    @staticmethod
    def _ensure_tenant_admin(actor: TenantAdmin) -> None:
        """Ensure actor is a tenant admin attached to a tenant."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant")

    @staticmethod
    def _ensure_teacher_actor(actor: Teacher) -> None:
        """Ensure actor is a teacher attached to a tenant."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Teacher is not attached to a tenant")

    @staticmethod
    async def create_teacher(
        db: AsyncSession,
        actor: TenantAdmin,
        teacher_data: TeacherCreate,
        background_tasks: BackgroundTasks | None = None,
    ) -> Teacher:
        """Create a teacher actor and attach an AuthIdentity."""

        TeacherService._ensure_tenant_admin(actor)

        normalized_email = TeacherService._normalize_email(teacher_data.email)
        normalized_staff_id = normalize_staff_id(teacher_data.staff_id)

        await AuthIdentityService.ensure_identifier_available(
            db=db,
            identifier=normalized_email,
            identifier_type=IdentifierType.EMAIL,
        )

        existing_teacher_email = await TeacherRepository.get_by_email(
            db=db,
            email=normalized_email,
        )
        if existing_teacher_email is not None:
            raise ConflictException(detail="A teacher with this email already exists")

        if normalized_staff_id is not None:
            staff_id_exists = await TeacherRepository.staff_id_exists(
                db=db,
                tenant_id=actor.tenant_id,
                staff_id=normalized_staff_id,
            )
            if staff_id_exists:
                raise ConflictException(detail="A teacher with this staff ID already exists")

        subject_ids = []
        unique_subject_ids = []

        tenant = await TenantRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
        )
        if tenant is None:
            raise NotFoundException(detail="Tenant not found")

        temporary_password = secrets.token_urlsafe(32)

        teacher = Teacher(
            tenant_id=actor.tenant_id,
            email=normalized_email,
            password_hash=hash_password(temporary_password),
            first_name=teacher_data.first_name,
            last_name=teacher_data.last_name,
            staff_id=normalized_staff_id,
            qualification=teacher_data.qualification,
            specialization=teacher_data.specialization,
            account_status=TeacherAccountStatus.PENDING,
            status=TeacherStatus.ACTIVE,
            is_verified=False,
            is_active=True,
        )

        try:
            created_teacher = await TeacherRepository.create_teacher(
                db=db,
                teacher=teacher,
            )

            await AuthIdentityService.create_for_actor(
                db=db,
                tenant_id=actor.tenant_id,
                payload=AuthIdentityCreate(
                    identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                    actor_type=ActorType.TEACHER,
                    actor_id=created_teacher.id,
                    is_active=True,
                ),
            )

            invite_link = await UserInviteService.create_invite_record(
                db=db,
                email=normalized_email,
                tenant_id=actor.tenant_id,
            )

            await db.commit()

            await UserInviteService.send_invite_email(
                email=normalized_email,
                user_name=(
                    " ".join(
                        part
                        for part in [teacher.first_name, teacher.last_name]
                        if part
                    ).strip()
                    or normalized_email
                ),
                school_name=tenant.school_name,
                invite_link=invite_link,
                background_tasks=background_tasks,
            )

            refreshed_teacher = await TeacherRepository.get_teacher_by_id(
                db=db,
                tenant_id=actor.tenant_id,
                teacher_id=created_teacher.id,
            )

            if not refreshed_teacher:
                raise NotFoundException(detail="Teacher not found after creation.")

            return refreshed_teacher

        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException(
                detail="Teacher creation failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def get_teacher(
        db: AsyncSession,
        actor: TenantAdmin,
        teacher_id: UUID,
    ) -> Teacher:
        """Return a teacher within the tenant admin's tenant."""

        TeacherService._ensure_tenant_admin(actor)

        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_id=teacher_id,
        )

        if not teacher:
            raise NotFoundException(detail="Teacher not found")

        return teacher

    @staticmethod
    async def get_my_subjects(
        db: AsyncSession,
        actor: Teacher,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Subject], int]:
        """Return only the subjects assigned to the current teacher."""

        TeacherService._ensure_teacher_actor(actor)

        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_id=actor.id,
        )

        if not teacher:
            raise NotFoundException(detail="Teacher profile not found.")

        return await SubjectRepository.list_subjects_for_teacher(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_id=teacher.id,
            skip=skip,
            limit=min(limit, 100),
            is_active=is_active,
            search=search,
        )

    @staticmethod
    async def get_my_teacher_profile(
        db: AsyncSession,
        actor: Teacher,
    ) -> Teacher:
        """Return the current teacher profile."""

        TeacherService._ensure_teacher_actor(actor)
        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_id=actor.id,
        )
        if not teacher:
            raise NotFoundException(detail="Teacher profile not found.")
        return teacher
