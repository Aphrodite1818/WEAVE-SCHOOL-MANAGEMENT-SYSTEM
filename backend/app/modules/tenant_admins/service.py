# ======================================#
#       tenant_admins/service.py       #
# ======================================#

"""Tenant admins service layer."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_password
from app.core.exceptions import ConflictException, NotFoundException
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.auth.account_email_guard import AccountEmailGuard
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import Parent, ParentInvitation, ParentInvitationStatus
from app.modules.students.models import (
    Student,
    StudentParentLinkRequest,
    StudentParentLinkRequestStatus,
    StudentProfileStatus,
)
from app.modules.subjects.models import Subject
from app.modules.teachers.models import (
    Teacher,
    TeacherInvitation,
    TeacherInvitationStatus,
)
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.modules.tenant_admins.schemas import (
    TenantAdminCreate,
    TenantAdminResponse,
    TenantAdminUpdate,
)
from app.tenant_management.models import Tenant


class TenantAdminService:
    """Business logic for handling tenant admin accounts"""

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    async def create_tenant_admin(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: TenantAdminCreate,
        create_auth_identity: bool = True,
    ) -> TenantAdminResponse:
        """Create a tenant admin account for a tenant"""

        normalized_email = TenantAdminService._normalize_email(email=payload.email)

        normalized_email = await AccountEmailGuard.ensure_not_superadmin_email(
            db=db, email=normalized_email
        )

        existing_admin = await TenantAdminRepository.get_by_email(db=db, email=normalized_email)

        if existing_admin:
            raise ConflictException("A tenant admin with this email already exists")

        await AuthIdentityService.ensure_identifier_available(
            db=db, identifier=normalized_email, identifier_type=IdentifierType.EMAIL
        )

        admin = TenantAdmin(
            tenant_id=tenant_id,
            email=normalized_email,
            password_hash=hash_password(payload.password),
            account_status=TenantAdminStatus.PENDING,
            is_verified=False,
            is_active=True,
        )

        created_admin = await TenantAdminRepository.create(db=db, admin=admin)

        if create_auth_identity:
            await AuthIdentityService.create_for_actor(
                db=db,
                tenant_id=tenant_id,
                payload=AuthIdentityCreate(
                    identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                    actor_type=ActorType.TENANT_ADMIN,
                    actor_id=created_admin.id,
                    is_active=True,
                ),
            )

        return TenantAdminResponse.model_validate(created_admin)

    @staticmethod
    async def get_by_id(db: AsyncSession, admin_id: uuid.UUID) -> TenantAdminResponse:
        """Return tenant admin by ID"""

        admin = await TenantAdminRepository.get_by_id(db=db, admin_id=admin_id)

        if admin is None:
            raise NotFoundException("Tenant admin not found")

        return TenantAdminResponse.model_validate(admin)

    @staticmethod
    async def get_by_tenant_id(db: AsyncSession, tenant_id: uuid.UUID) -> TenantAdminResponse:
        """Return the tenant admin attached to a tenant"""

        admin = await TenantAdminRepository.get_by_tenant_id(db=db, tenant_id=tenant_id)

        if admin is None:
            raise NotFoundException("Tenan admin not found")

        return TenantAdminResponse.model_validate(admin)

    @staticmethod
    async def update_tenant_admin(
        db: AsyncSession, *, admin_id: uuid.UUID, payload: TenantAdminUpdate
    ) -> TenantAdminResponse | None:
        """Update a tenant admin account"""

        admin = await TenantAdminRepository.get_by_id(db=db, admin_id=admin_id)

        if admin is None:
            raise NotFoundException("Tenant admin not found")

        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            return TenantAdminResponse.model_validate(admin)

        if "email" in update_data and update_data["email"] is not None:
            normalized_email = TenantAdminService._normalize_email(update_data["email"])

            normalized_email = await AccountEmailGuard.ensure_not_superadmin_email(
                db=db, email=normalized_email
            )

            existing_admin = await TenantAdminRepository.get_by_email(db=db, email=normalized_email)
            if existing_admin is not None and existing_admin.id != admin.id:
                raise ConflictException("A tenant admin witht this email already exists")

            await AuthIdentityService.update_identifier(
                db=db,
                actor_type=ActorType.TENANT_ADMIN,
                actor_id=admin.id,
                new_identifier=normalized_email,
                identifier_type=IdentifierType.EMAIL,
            )

            admin.email = normalized_email

        if "password" in update_data and update_data["password"] is not None:
            admin.password_hash = hash_password(update_data["password"])

        if "account_status" in update_data and update_data["account_status"] is not None:
            admin.account_status = update_data["account_status"]

        if "is_verified" in update_data and update_data["is_verified"] is not None:
            admin.is_verified = update_data["is_verified"]

        if "is_active" in update_data and update_data["is_active"] is not None:
            admin.is_active = update_data["is_active"]

        if admin.is_active is False:
            await AuthIdentityService.deactivate_for_actor(
                db=db,
                actor_type=ActorType.TENANT_ADMIN,
                actor_id=admin.id,
            )

        if "last_login_at" in update_data and update_data["last_login_at"] is not None:
            admin.last_login_at = update_data["last_login_at"]

        saved_admin = await TenantAdminRepository.save(db=db, admin=admin)

        return TenantAdminResponse.model_validate(saved_admin)

    @staticmethod
    async def mark_verified(
        db: AsyncSession,
        *,
        admin_id: uuid.UUID,
    ) -> TenantAdminResponse:
        """Mark tenant admin as verified and active."""

        admin = await TenantAdminRepository.get_by_id(
            db=db,
            admin_id=admin_id,
        )

        if admin is None:
            raise NotFoundException("Tenant admin not found.")

        admin.is_verified = True
        admin.account_status = TenantAdminStatus.ACTIVE
        admin.is_active = True

        saved_admin = await TenantAdminRepository.save(
            db=db,
            admin=admin,
        )

        return TenantAdminResponse.model_validate(saved_admin)

    @staticmethod
    async def update_last_login(
        db: AsyncSession,
        *,
        admin_id: uuid.UUID,
    ) -> TenantAdminResponse:
        """Update tenant admin last login timestamp."""

        admin = await TenantAdminRepository.get_by_id(
            db=db,
            admin_id=admin_id,
        )

        if admin is None:
            raise NotFoundException("Tenant admin not found.")

        admin.last_login_at = datetime.now(timezone.utc)

        saved_admin = await TenantAdminRepository.save(
            db=db,
            admin=admin,
        )

        return TenantAdminResponse.model_validate(saved_admin)

    @staticmethod
    async def get_analytics_overview(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
    ) -> dict[str, object]:
        """Return tenant-scoped analytics for the admin dashboard."""

        total_students = (
            await db.execute(
                select(func.count()).select_from(Student).where(Student.tenant_id == tenant_id)
            )
        ).scalar_one()
        total_teachers = (
            await db.execute(
                select(func.count()).select_from(Teacher).where(Teacher.tenant_id == tenant_id)
            )
        ).scalar_one()
        total_parents = (
            await db.execute(
                select(func.count()).select_from(Parent).where(Parent.tenant_id == tenant_id)
            )
        ).scalar_one()
        total_classes = (
            await db.execute(
                select(func.count()).select_from(ClassRoom).where(ClassRoom.tenant_id == tenant_id)
            )
        ).scalar_one()
        total_subjects = (
            await db.execute(
                select(func.count()).select_from(Subject).where(Subject.tenant_id == tenant_id)
            )
        ).scalar_one()
        student_profiles_complete = (
            await db.execute(
                select(func.count())
                .select_from(Student)
                .where(
                    Student.tenant_id == tenant_id,
                    Student.profile_status == StudentProfileStatus.COMPLETE,
                )
            )
        ).scalar_one()
        student_profiles_incomplete = total_students - student_profiles_complete
        pending_teacher_invites = (
            await db.execute(
                select(func.count())
                .select_from(TeacherInvitation)
                .where(
                    TeacherInvitation.tenant_id == tenant_id,
                    TeacherInvitation.status == TeacherInvitationStatus.PENDING,
                )
            )
        ).scalar_one()
        pending_parent_invites = (
            await db.execute(
                select(func.count())
                .select_from(ParentInvitation)
                .where(
                    ParentInvitation.tenant_id == tenant_id,
                    ParentInvitation.status == ParentInvitationStatus.PENDING,
                )
            )
        ).scalar_one()
        pending_parent_link_requests = (
            await db.execute(
                select(func.count())
                .select_from(StudentParentLinkRequest)
                .where(
                    StudentParentLinkRequest.tenant_id == tenant_id,
                    StudentParentLinkRequest.status == StudentParentLinkRequestStatus.PENDING,
                )
            )
        ).scalar_one()

        return {
            "stats": {
                "total_students": total_students,
                "total_teachers": total_teachers,
                "total_parents": total_parents,
                "total_classes": total_classes,
                "total_subjects": total_subjects,
                "student_profiles_complete": student_profiles_complete,
                "student_profiles_incomplete": student_profiles_incomplete,
                "pending_teacher_invites": pending_teacher_invites,
                "pending_parent_invites": pending_parent_invites,
                "pending_parent_link_requests": pending_parent_link_requests,
            },
            "charts": {
                "population_breakdown": [
                    {"label": "students", "value": total_students},
                    {"label": "teachers", "value": total_teachers},
                    {"label": "parents", "value": total_parents},
                    {"label": "classes", "value": total_classes},
                    {"label": "subjects", "value": total_subjects},
                ],
                "profile_completion": [
                    {"label": "complete", "value": student_profiles_complete},
                    {"label": "incomplete", "value": student_profiles_incomplete},
                ],
                "pending_workflows": [
                    {"label": "teacher_invites", "value": pending_teacher_invites},
                    {"label": "parent_invites", "value": pending_parent_invites},
                    {
                        "label": "parent_link_requests",
                        "value": pending_parent_link_requests,
                    },
                ],
            },
        }
