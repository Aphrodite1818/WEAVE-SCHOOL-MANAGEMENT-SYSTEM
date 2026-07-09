import secrets
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_password
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.auth.service import UserInviteService
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.parents.repository import ParentRepository
from app.modules.parents.schemas import (
    ParentCreate,
    ParentLinkedStudentResponse,
    ParentOnboardingStatusResponse,
    ParentOnboardingUpdate,
    ParentResponse,
    ParentSelfUpdate,
    ParentUpdate,
)
from app.modules.students.repository import StudentParentLinkRepository
from app.modules.students.schemas import StudentParentLinkResponse, StudentResponse
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository
from app.modules.auth.account_email_guard import AccountEmailGuard


class ParentService:
    """Business logic for parent actors."""

    @staticmethod
    def _normalize_email(email: str) -> str:
        """Normalize a parent email address."""

        return email.strip().lower()

    @staticmethod
    def _ensure_tenant_admin(actor: TenantAdmin) -> None:
        """Ensure the actor is a tenant admin."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant")

    @staticmethod
    def _ensure_parent_actor(actor: Parent) -> None:
        """Ensure the actor is a parent attached to a tenant."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Parent is not attached to a tenant")

    @staticmethod
    async def create_parent(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ParentCreate,
        background_tasks: BackgroundTasks | None = None,
    ) -> ParentResponse:
        """Create a parent actor and attach an AuthIdentity."""

        ParentService._ensure_tenant_admin(actor)

        normalized_email = ParentService._normalize_email(payload.email)

        normalized_email = await AccountEmailGuard.ensure_not_superadmin_email(
            db = db ,
            email = normalized_email
        )

        await AuthIdentityService.ensure_identifier_available(
            db=db,
            identifier=normalized_email,
            identifier_type=IdentifierType.EMAIL,
        )

        if await ParentRepository.email_exists(db=db, email=normalized_email):
            raise ConflictException(detail="A parent with this email already exists")

        tenant = await TenantRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
        )
        if tenant is None:
            raise NotFoundException(detail="Tenant not found")

        temporary_password = secrets.token_urlsafe(32)

        parent = Parent(
            tenant_id=actor.tenant_id,
            email=normalized_email,
            password_hash=hash_password(temporary_password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone_number=payload.phone_number,
            occupation=payload.occupation,
            address=payload.address,
            emergency_phone=payload.emergency_phone,
            account_status=ParentAccountStatus.PENDING,
            is_verified=False,
            is_active=True,
            last_login_at=None,
        )

        try:
            created_parent = await ParentRepository.create_parent(db=db, parent=parent)

            await AuthIdentityService.create_for_actor(
                db=db,
                tenant_id=actor.tenant_id,
                payload=AuthIdentityCreate(
                    identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                    actor_type=ActorType.PARENT,
                    actor_id=created_parent.id,
                    is_active=True,
                ),
            )

            invite_link = await UserInviteService.create_invite_record(
                db=db,
                email=normalized_email,
                tenant_id=actor.tenant_id,
            )

            await db.commit()
            await db.refresh(created_parent)

            await UserInviteService.send_invite_email(
                email=normalized_email,
                user_name=(
                    " ".join(
                        part
                        for part in [created_parent.first_name, created_parent.last_name]
                        if part
                    ).strip()
                    or normalized_email
                ),
                school_name=tenant.school_name,
                invite_link=invite_link,
                background_tasks=background_tasks,
            )

            return ParentResponse.model_validate(created_parent)
        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException(
                detail="Parent creation failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def get_parent_profile(
        db: AsyncSession,
        actor: TenantAdmin | Parent,
        parent_id: UUID,
    ) -> ParentResponse:
        """Get a parent profile by ID within the current tenant."""

        tenant_id = actor.tenant_id
        if not tenant_id:
            raise ForbiddenException(detail="Actor is not attached to a tenant")

        parent = await ParentRepository.get_parent_by_id(
            db=db,
            tenant_id=tenant_id,
            parent_id=parent_id,
        )
        if parent is None:
            raise NotFoundException(detail="Parent profile not found")

        if isinstance(actor, Parent) and parent.id != actor.id:
            raise ForbiddenException(detail="You are not allowed to view this parent profile")

        return ParentResponse.model_validate(parent)

    @staticmethod
    async def get_my_parent_profile(
        db: AsyncSession,
        actor: Parent,
    ) -> ParentResponse:
        """Get the current parent profile."""

        ParentService._ensure_parent_actor(actor)
        parent = await ParentRepository.get_parent_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=actor.id,
        )
        if parent is None:
            raise NotFoundException(detail="Parent profile not found")
        return ParentResponse.model_validate(parent)

    @staticmethod
    async def update_my_parent_profile(
        db: AsyncSession,
        actor: Parent,
        payload: ParentOnboardingUpdate,
    ) -> ParentResponse:
        """Allow a parent to update their own profile."""

        ParentService._ensure_parent_actor(actor)

        parent = await ParentRepository.get_parent_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=actor.id,
        )
        if parent is None:
            raise NotFoundException(detail="Parent profile not found")

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException(detail="No update data provided")

        for field, value in update_data.items():
            setattr(parent, field, value)

        updated_parent = await ParentRepository.save(db=db, parent=parent)
        await db.commit()
        await db.refresh(updated_parent)
        return ParentResponse.model_validate(updated_parent)

    @staticmethod
    async def get_my_onboarding_status(
        db: AsyncSession,
        actor: Parent,
    ) -> ParentOnboardingStatusResponse:
        """Return the current parent onboarding status."""

        parent = await ParentService.get_my_parent_profile(
            db=db,
            actor=actor,
        )

        return ParentOnboardingStatusResponse(
            actor_type="parent",
            parent_id=parent.id,
            onboarding_required=not parent.profile_completed,
            profile_completed=parent.profile_completed,
            completion_target="parent",
            required_fields=["first_name", "last_name"],
            current_values={
                "email": parent.email,
                "first_name": parent.first_name,
                "last_name": parent.last_name,
                "phone_number": parent.phone_number,
                "occupation": parent.occupation,
                "address": parent.address,
                "emergency_phone": parent.emergency_phone,
            },
        )

    @staticmethod
    async def get_all_parents(
        db: AsyncSession,
        actor: TenantAdmin,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
    ) -> tuple[list[ParentResponse], int]:
        """Get a paginated list of parents for a tenant."""

        ParentService._ensure_tenant_admin(actor)
        parents, total = await ParentRepository.list_all_parents(
            db=db,
            tenant_id=actor.tenant_id,
            skip=skip,
            limit=min(limit, 100),
            search=search,
        )
        return [ParentResponse.model_validate(parent) for parent in parents], total

    @staticmethod
    async def get_my_linked_students(
        db: AsyncSession,
        actor: Parent,
    ) -> tuple[list[ParentLinkedStudentResponse], int]:
        """Get students linked to the logged-in parent."""

        ParentService._ensure_parent_actor(actor)

        links = await StudentParentLinkRepository.get_by_parent_id(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=actor.id,
        )

        linked_students = [
            ParentLinkedStudentResponse(
                student=StudentResponse.model_validate(link.student),
                link=StudentParentLinkResponse.model_validate(link),
            )
            for link in links
            if link.student is not None
        ]

        return linked_students, len(linked_students)

    @staticmethod
    async def update_parent_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        parent_id: UUID,
        payload: ParentUpdate,
    ) -> ParentResponse:
        """Update a parent profile as tenant admin."""

        ParentService._ensure_tenant_admin(actor)

        parent = await ParentRepository.get_parent_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=parent_id,
        )
        if parent is None:
            raise NotFoundException(detail="Parent profile not found")

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException(detail="No update data provided")

        if "email" in update_data and update_data["email"] is not None:
            normalized_email = ParentService._normalize_email(update_data["email"])
            normalized_email = await AccountEmailGuard.ensure_not_superadmin_email(
                db = db ,
                email = normalized_email
            )
            if normalized_email != parent.email:
                await AuthIdentityService.ensure_identifier_available(
                    db=db,
                    identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                )
                if await ParentRepository.email_exists(
                    db=db,
                    email=normalized_email,
                    exclude_parent_id=parent.id,
                ):
                    raise ConflictException(detail="A parent with this email already exists")

                await AuthIdentityService.update_identifier(
                    db=db,
                    actor_type=ActorType.PARENT,
                    actor_id=parent.id,
                    new_identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                )
                update_data["email"] = normalized_email

        if "password" in update_data and update_data["password"] is not None:
            update_data["password_hash"] = hash_password(update_data.pop("password"))

        if "is_active" in update_data and update_data["is_active"] is False:
            await AuthIdentityService.deactivate_for_actor(
                db=db,
                actor_type=ActorType.PARENT,
                actor_id=parent.id,
            )

        if (
            "account_status" in update_data
            and update_data["account_status"] == ParentAccountStatus.INACTIVE
        ):
            await AuthIdentityService.deactivate_for_actor(
                db=db,
                actor_type=ActorType.PARENT,
                actor_id=parent.id,
            )

        try:
            for field, value in update_data.items():
                setattr(parent, field, value)

            updated_parent = await ParentRepository.save(db=db, parent=parent)
            await db.commit()
            await db.refresh(updated_parent)
            return ParentResponse.model_validate(updated_parent)
        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException(
                detail="Parent update failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def delete_parent_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        parent_id: UUID,
    ) -> None:
        """Delete a parent profile."""

        ParentService._ensure_tenant_admin(actor)

        parent = await ParentRepository.get_parent_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=parent_id,
        )
        if parent is None:
            raise NotFoundException(detail="Parent profile not found")

        await AuthIdentityService.deactivate_for_actor(
            db=db,
            actor_type=ActorType.PARENT,
            actor_id=parent.id,
        )
        await ParentRepository.delete_parent(db=db, parent=parent)
        await db.commit()
