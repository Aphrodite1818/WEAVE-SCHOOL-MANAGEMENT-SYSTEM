# ====================================== #
#              service.py               #
# ====================================== #

"""Teacher service layer. for weave"""

from locale import normalize
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
from app.modules.auth.account_email_guard import AccountEmailGuard
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

        normalized_email = await AccountEmailGuard.ensure_not_superadmin_email(
            db = db ,
            email = normalized_email,
        )

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
            await AuthIdentityService.invalidate_after_commit(db)

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
            AuthIdentityService.discard_pending_invalidations(db)
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

    @staticmethod
    async def update_my_teacher_profile(
        db: AsyncSession,
        actor: Teacher,
        teacher_data: TeacherOnboardingUpdate,
    ) -> Teacher:
        """Allow a teacher to update their own profile fields."""

        teacher = await TeacherService.get_my_teacher_profile(
            db=db,
            actor=actor,
        )

        update_data = teacher_data.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException(detail="No update data provided")

        if "staff_id" in update_data:
            normalized_staff_id = normalize_staff_id(update_data["staff_id"])
            update_data["staff_id"] = normalized_staff_id

            if normalized_staff_id is not None and normalized_staff_id != teacher.staff_id:
                staff_id_exists = await TeacherRepository.staff_id_exists(
                    db=db,
                    tenant_id=actor.tenant_id,
                    staff_id=normalized_staff_id,
                    exclude_teacher_id=teacher.id,
                )

                if staff_id_exists:
                    raise ConflictException(detail="A teacher with this staff ID already exists")

        for field, value in update_data.items():
            setattr(teacher, field, value)

        updated_teacher = await TeacherRepository.save(
            db=db,
            teacher=teacher,
        )

        await db.commit()
        await db.refresh(updated_teacher)

        return updated_teacher

    @staticmethod
    async def get_my_onboarding_status(
        db: AsyncSession,
        actor: Teacher,
    ) -> TeacherOnboardingStatusResponse:
        """Return the current teacher onboarding state."""

        teacher = await TeacherService.get_my_teacher_profile(
            db=db,
            actor=actor,
        )

        return TeacherOnboardingStatusResponse(
            actor_type="teacher",
            teacher_id=teacher.id,
            onboarding_required=not teacher.profile_completed,
            profile_completed=teacher.profile_completed,
            completion_target="teacher",
            required_fields=["first_name", "last_name"],
            current_values={
                "email": teacher.email,
                "first_name": teacher.first_name,
                "last_name": teacher.last_name,
                "qualification": teacher.qualification,
                "specialization": teacher.specialization,
            },
        )

    @staticmethod
    async def list_teachers(
        db: AsyncSession,
        actor: TenantAdmin,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
    ) -> tuple[list[Teacher], int]:
        """List teachers for a tenant."""

        TeacherService._ensure_tenant_admin(actor)
        limit = min(limit, 100)

        return await TeacherRepository.list_all_teachers(
            db=db,
            tenant_id=actor.tenant_id,
            skip=skip,
            limit=limit,
            search=search,
        )

    @staticmethod
    async def update_teacher(
        db: AsyncSession,
        actor: TenantAdmin,
        teacher_id: UUID,
        teacher_data: TeacherUpdate,
    ) -> Teacher:
        """Update teacher as tenant admin."""

        TeacherService._ensure_tenant_admin(actor)

        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            teacher_id=teacher_id,
            tenant_id=actor.tenant_id,
        )

        if not teacher:
            raise NotFoundException(detail="Teacher not found")

        update_data = teacher_data.model_dump(exclude_unset=True)

        if not update_data:
            raise BadRequestException(detail="No update data provided")

        if "email" in update_data and update_data["email"] is not None:
            normalized_email = TeacherService._normalize_email(update_data["email"])

            normalized_email = await AccountEmailGuard.ensure_not_superadmin_email(
                db = db ,
                email = normalized_email
            )

            if normalized_email != teacher.email:
                await AuthIdentityService.ensure_identifier_available(
                    db=db,
                    identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                )

                existing_teacher = await TeacherRepository.get_by_email(
                    db=db,
                    email=normalized_email,
                )

                if existing_teacher is not None and existing_teacher.id != teacher.id:
                    raise ConflictException(
                        detail="A teacher with this email already exists"
                    )

                await AuthIdentityService.update_identifier(
                    db=db,
                    actor_type=ActorType.TEACHER,
                    actor_id=teacher.id,
                    new_identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                )

                update_data["email"] = normalized_email

        if "staff_id" in update_data:
            normalized_staff_id = normalize_staff_id(update_data["staff_id"])
            update_data["staff_id"] = normalized_staff_id

            if normalized_staff_id is not None and normalized_staff_id != teacher.staff_id:
                staff_id_exists = await TeacherRepository.staff_id_exists(
                    db=db,
                    tenant_id=actor.tenant_id,
                    staff_id=normalized_staff_id,
                    exclude_teacher_id=teacher.id,
                )

                if staff_id_exists:
                    raise ConflictException(detail="A teacher with this staff ID already exists")

        if "password" in update_data and update_data["password"] is not None:
            update_data["password_hash"] = hash_password(update_data.pop("password"))

        if "is_active" in update_data and update_data["is_active"] is False:
            await AuthIdentityService.deactivate_for_actor(
                db=db,
                actor_type=ActorType.TEACHER,
                actor_id=teacher.id,
            )

        try:
            if update_data:
                for field, value in update_data.items():
                    setattr(teacher, field, value)

                teacher = await TeacherRepository.save(
                    db=db,
                    teacher=teacher,
                )

            await db.commit()
            await AuthIdentityService.invalidate_after_commit(db)

            updated_teacher = await TeacherRepository.get_teacher_by_id(
                db=db,
                tenant_id=actor.tenant_id,
                teacher_id=teacher.id,
            )

            if not updated_teacher:
                raise NotFoundException(detail="Teacher not found after update.")

            return updated_teacher

        except IntegrityError as exc:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)
            raise BadRequestException(
                detail="Teacher update failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def delete_teacher(
        db: AsyncSession,
        actor: TenantAdmin,
        teacher_id: UUID,
    ) -> None:
        """Archive teacher and remove subject links."""

        TeacherService._ensure_tenant_admin(actor)

        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_id=teacher_id,
        )

        if not teacher:
            raise NotFoundException(detail="Teacher not found")

        teacher.status = TeacherStatus.ARCHIVED
        teacher.is_active = False

        await AuthIdentityService.deactivate_for_actor(
            db=db,
            actor_type=ActorType.TEACHER,
            actor_id=teacher.id,
        )

        await TeacherRepository.save(db=db, teacher=teacher)

        await TeacherRepository.delete_all_teacher_subject_links(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_id=teacher.id,
        )

        await db.commit()
        await AuthIdentityService.invalidate_after_commit(db)
