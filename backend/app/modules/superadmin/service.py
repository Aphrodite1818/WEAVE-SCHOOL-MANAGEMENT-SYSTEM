import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.security import hash_auth_secret, hash_password, verify_password
from app.config.settings import settings
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException, UnauthorizedException
from app.core.utils.email import send_email
from app.core.utils.email_templates import get_tenant_invite_email_html, get_user_invite_email_html
from app.modules.auth.models import AuthPurpose, AuthRecord
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.parents.repository import ParentRepository
from app.modules.superadmin.models import SuperAdmin, SuperAdminInvite
from app.modules.superadmin.repository import SuperAdminRepository
from app.modules.superadmin.schemas import SuperadminInviteCreate
from app.modules.teachers.repository import TeacherRepository
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.tenant_management.models import Tenant, TenantStatus, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository
from app.tenant_management.schemas import TenantCreate, TenantStatusUpdate
from app.tenant_management.service import TenantService


logger = get_logger(__name__)


def _normalize_email(email: str) -> str:
    """Normalize the email address."""

    return email.strip().lower()


class SuperadminService:
    """Business logic for the superadmin domain."""

    @staticmethod
    def _build_invite_link(raw_token: str, frontend_app_url: str | None = None) -> str:
        """Build invite link."""

        base_url = (frontend_app_url or settings.FRONTEND_APP_URL).strip().rstrip("/")
        return f"{base_url}/invite?token={quote(raw_token, safe='')}"

    @staticmethod
    async def get_email_conflicts(
        db: AsyncSession,
        email: str,
    ) -> tuple[TenantAdmin | object | None, Tenant | None, SuperAdmin | None]:
        """Return email conflicts across tenant actors, tenants, and superadmins."""

        normalized_email = _normalize_email(email)
        existing_admin = await TenantAdminRepository.get_by_email(db, normalized_email)
        existing_teacher = await TeacherRepository.get_by_email(db, normalized_email)
        existing_parent = await ParentRepository.get_by_email(db, normalized_email)
        existing_tenant = await TenantRepository.get_by_email_including_deleted(db, normalized_email)
        existing_superadmin = await SuperAdminRepository.get_by_email(db, normalized_email)

        existing_actor = existing_admin or existing_teacher or existing_parent
        return existing_actor, existing_tenant, existing_superadmin

    @staticmethod
    async def authenticate_superadmin(
        db: AsyncSession,
        *,
        email: str,
        password: str,
    ) -> SuperAdmin | None:
        """Perform authenticate superadmin."""

        superadmin = await SuperAdminRepository.get_by_email(db, email)
        if superadmin is None:
            return None
        if not verify_password(password, superadmin.password_hash):
            raise UnauthorizedException("Invalid email or password")
        if not superadmin.is_active:
            raise UnauthorizedException("Superadmin account is not active")

        superadmin.last_login_at = datetime.now(timezone.utc)
        await SuperAdminRepository.save(db, superadmin)
        await db.commit()
        return superadmin

    @staticmethod
    async def list_superadmins(
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SuperAdmin]:
        """List superadmins."""

        return await SuperAdminRepository.list(db, skip=skip, limit=limit)

    @staticmethod
    async def create_tenant(
        db: AsyncSession,
        payload: TenantCreate,
        background_tasks: BackgroundTasks | None = None,
        frontend_app_url: str | None = None,
    ) -> Tenant:
        """Create tenant and a pending tenant admin actor."""

        normalized_email = _normalize_email(payload.email)
        existing_actor, existing_tenant, existing_superadmin = await SuperadminService.get_email_conflicts(
            db,
            normalized_email,
        )

        if existing_actor or existing_superadmin or existing_tenant:
            raise ConflictException("A school or account with this email already exists")

        if payload.school_bot_whatssap_number:
            number_exists = await TenantRepository.school_bot_whatssap_number_exists(
                db,
                payload.school_bot_whatssap_number,
            )
            if number_exists:
                raise ConflictException("This WhatsApp number is already in use by another school")

        if payload.admission_number_prefix:
            existing_tenant_with_prefix = await TenantRepository.get_by_admission_number_prefix(
                db,
                payload.admission_number_prefix,
            )
            if existing_tenant_with_prefix is not None:
                raise ConflictException("Prefix not available")

        slug = await TenantService._unique_slug(db, payload.school_name)
        tenant_data = payload.model_dump(mode="json", exclude={"log_slug_preview"})
        tenant_data["email"] = normalized_email

        try:
            tenant = Tenant(
                **tenant_data,
                slug=slug,
                status=TenantStatus.INACTIVE,
                verification_status=TenantVerificationStatus.PENDING_VERIFICATION,
            )
            db.add(tenant)
            await db.flush()

            admin = TenantAdmin(
                email=normalized_email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                account_status=TenantAdminStatus.PENDING,
                tenant_id=tenant.id,
                is_verified=False,
                is_active=True,
            )
            await TenantAdminRepository.create(db, admin)

            await AuthIdentityService.create_for_actor(
                db=db,
                tenant_id=tenant.id,
                payload=AuthIdentityCreate(
                    identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                    actor_type=ActorType.TENANT_ADMIN,
                    actor_id=admin.id,
                    is_active=True,
                ),
            )

            raw_token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(
                hours=settings.TENANT_ACTIVATION_EXPIRATION_HOURS
            )
            db.add(
                AuthRecord(
                    email=admin.email,
                    hashed_value=hash_auth_secret(raw_token),
                    purpose=AuthPurpose.TENANT_ACTIVATION,
                    expires_at=expires_at,
                    tenant_id=tenant.id,
                )
            )
            invite_link = SuperadminService._build_invite_link(
                raw_token,
                frontend_app_url=frontend_app_url,
            )

            await db.commit()
            await AuthIdentityService.invalidate_after_commit(db)
            await db.refresh(tenant)
        except Exception:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)
            logger.exception("Superadmin tenant creation failed", extra={"email": normalized_email})
            raise

        subject = f"Activate your {tenant.school_name} administrator account"
        html_body = get_tenant_invite_email_html(tenant.school_name, invite_link)
        if background_tasks is not None:
            background_tasks.add_task(
                send_email,
                to_email=normalized_email,
                subject=subject,
                body=html_body,
                is_html=True,
            )
        else:
            email_sent = await send_email(
                to_email=normalized_email,
                subject=subject,
                body=html_body,
                is_html=True,
            )
            if not email_sent:
                raise BadRequestException("Unable to send activation email. Please try again.")

        return tenant

    @staticmethod
    async def list_tenants(
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        include_deleted: bool = True,
    ) -> list[Tenant]:
        """List tenants."""

        return await TenantRepository.get_all(
            db,
            skip=skip,
            limit=limit,
            include_deleted=include_deleted,
        )

    @staticmethod
    async def get_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        include_deleted: bool = True,
    ) -> Tenant:
        """Return tenant."""

        tenant = (
            await TenantRepository.get_by_id_including_deleted(db, tenant_id)
            if include_deleted
            else await TenantRepository.get_by_id(db, tenant_id)
        )
        if not tenant:
            raise NotFoundException("Tenant not found")
        return tenant

    @staticmethod
    async def update_tenant_status(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TenantStatusUpdate,
    ) -> Tenant:
        """Update tenant status."""

        tenant = await TenantRepository.get_by_id_including_deleted(db, tenant_id)
        if not tenant:
            raise NotFoundException("Tenant not found")
        if tenant.is_deleted:
            raise BadRequestException("Deleted tenants must be restored before status updates.")

        tenant.status = payload.status
        updated_tenant = await TenantRepository.save(db, tenant)

        await db.commit()
        await db.refresh(updated_tenant)
        return updated_tenant

    @staticmethod
    async def restore_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
        """Perform restore tenant."""

        tenant = await TenantRepository.get_by_id_including_deleted(db, tenant_id)
        if not tenant:
            raise NotFoundException("Tenant not found")
        if not tenant.is_deleted:
            raise BadRequestException("Tenant is not deleted")

        tenant.is_deleted = False
        tenant.deleted_at = None
        restored_tenant = await TenantRepository.save(db, tenant)

        await db.commit()
        await db.refresh(restored_tenant)
        return restored_tenant

    @staticmethod
    async def delete_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, str]:
        """Delete tenant."""

        tenant = await TenantRepository.get_by_id(db, tenant_id)
        if not tenant:
            raise NotFoundException("Tenant not found")
        tenant.is_deleted = True
        tenant.deleted_at = datetime.now(timezone.utc)
        await TenantRepository.save(db, tenant)
        await db.commit()
        return {"detail": "Tenant successfully deleted"}

    @staticmethod
    async def invite_superadmin(
        db: AsyncSession,
        *,
        invited_by: SuperAdmin,
        payload: SuperadminInviteCreate,
        background_tasks: BackgroundTasks | None = None,
        frontend_app_url: str | None = None,
    ) -> dict[str, str]:
        """Perform invite superadmin."""

        normalized_email = _normalize_email(payload.email)
        existing_actor, existing_tenant, existing_superadmin = await SuperadminService.get_email_conflicts(
            db,
            normalized_email,
        )

        if existing_actor or existing_tenant:
            raise ConflictException("A school or account with this email already exists")
        if existing_superadmin is not None:
            raise ConflictException("A superadmin account with this email already exists")

        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.TENANT_ACTIVATION_EXPIRATION_HOURS
        )

        try:
            await SuperAdminRepository.delete_active_invites_for_email(db, normalized_email)
            await SuperAdminRepository.create_invite(
                db,
                SuperAdminInvite(
                    email=normalized_email,
                    hashed_token=hash_auth_secret(raw_token),
                    invited_by_superadmin_id=invited_by.id,
                    expires_at=expires_at,
                    is_used=False,
                ),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Superadmin invite failed", extra={"email": normalized_email})
            raise

        invite_link = SuperadminService._build_invite_link(raw_token, frontend_app_url=frontend_app_url)
        subject = f"Set up your {settings.APP_NAME} superadmin account"
        html_body = get_user_invite_email_html(normalized_email, settings.APP_NAME, invite_link)

        if background_tasks is not None:
            background_tasks.add_task(
                send_email,
                to_email=normalized_email,
                subject=subject,
                body=html_body,
                is_html=True,
            )
        else:
            email_sent = await send_email(
                to_email=normalized_email,
                subject=subject,
                body=html_body,
                is_html=True,
            )
            if not email_sent:
                raise BadRequestException("Unable to send invite email. Please try again.")

        return {"detail": "Superadmin invite created and emailed successfully."}

    @staticmethod
    async def get_analytics_overview(
        db: AsyncSession,
    ) -> dict[str, object]:
        """Return platform analytics for the superadmin dashboard."""

        total_tenants = (
            await db.execute(select(func.count()).select_from(Tenant))
        ).scalar_one()
        active_tenants = (
            await db.execute(
                select(func.count()).select_from(Tenant).where(
                    Tenant.is_deleted.is_(False),
                    Tenant.verification_status == TenantVerificationStatus.ACTIVE,
                    Tenant.status == TenantStatus.ACTIVE,
                )
            )
        ).scalar_one()
        pending_verification = (
            await db.execute(
                select(func.count()).select_from(Tenant).where(
                    Tenant.is_deleted.is_(False),
                    Tenant.verification_status == TenantVerificationStatus.PENDING_VERIFICATION,
                )
            )
        ).scalar_one()
        rejected_verification = (
            await db.execute(
                select(func.count()).select_from(Tenant).where(
                    Tenant.is_deleted.is_(False),
                    Tenant.verification_status == TenantVerificationStatus.REJECTED,
                )
            )
        ).scalar_one()
        total_tenant_admins = (
            await db.execute(select(func.count()).select_from(TenantAdmin))
        ).scalar_one()

        growth_period = func.date_trunc("month", Tenant.created_at)
        growth_rows = (
            await db.execute(
                select(
                    growth_period.label("period"),
                    func.count(Tenant.id).label("value"),
                )
                .group_by(growth_period)
                .order_by(growth_period)
            )
        ).all()

        status_breakdown = []
        for status in TenantStatus:
            value = (
                await db.execute(
                    select(func.count()).select_from(Tenant).where(
                        Tenant.is_deleted.is_(False),
                        Tenant.status == status,
                    )
                )
            ).scalar_one()
            status_breakdown.append({"label": status.value, "value": value})

        return {
            "stats": {
                "total_tenants": total_tenants,
                "active_tenants": active_tenants,
                "pending_verification": pending_verification,
                "rejected_verification": rejected_verification,
                "total_tenant_admins": total_tenant_admins,
            },
            "charts": {
                "tenant_growth": [
                    {
                        "label": row.period.strftime("%Y-%m") if row.period else "",
                        "value": row.value,
                    }
                    for row in growth_rows
                ],
                "verification_breakdown": [
                    {"label": "active", "value": active_tenants},
                    {"label": "pending_verification", "value": pending_verification},
                    {"label": "rejected", "value": rejected_verification},
                ],
                "status_breakdown": status_breakdown,
            },
        }
