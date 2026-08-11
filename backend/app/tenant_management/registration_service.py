"""Tenant registration workflow with replaceable pending passwords."""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.security import hash_password
from app.core.exceptions import ConflictException, TooManyRequestsException
from app.modules.auth.account_email_guard import AccountEmailGuard
from app.modules.auth.models import AuthPurpose
from app.modules.auth.schemas import RequestOTP
from app.modules.auth.service import OTPService
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.modules.tenant_admins.schemas import TenantAdminCreate
from app.modules.tenant_admins.service import TenantAdminService
from app.tenant_management.models import SubscriptionPlan, Tenant, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository
from app.tenant_management.schemas import TenantRegisterRequest
from app.tenant_management.service import (
    EmailRegistrationState,
    TenantService,
    _normalize_email,
    _normalize_school_name,
)

logger = get_logger(__name__)


class TenantRegistrationService:
    """Register tenants and allow pending registrations to replace passwords."""

    @staticmethod
    def _require_replaceable_pending_admin(
        *,
        admin: TenantAdmin | None,
    ) -> TenantAdmin:
        if (
            admin is None
            or admin.account_status != TenantAdminStatus.PENDING
            or admin.is_verified
            or not admin.is_active
        ):
            raise ConflictException(
                "This pending registration is inconsistent. Please contact support."
            )
        return admin

    @staticmethod
    async def _replace_pending_password(
        db: AsyncSession,
        *,
        admin: TenantAdmin,
        password: str,
        selected_plan_code: str | None = None,
        billing_interval: str = "term",
    ) -> None:
        admin.password_hash = hash_password(password)
        admin.account_status = TenantAdminStatus.PENDING
        admin.is_verified = False
        admin.is_active = True
        tenant = await TenantRepository.get_by_id(db, admin.tenant_id, lock=True)
        if tenant is not None:
            tenant.initial_plan_intent = (
                SubscriptionPlan(selected_plan_code) if selected_plan_code else None
            )
            flags = dict(tenant.feature_flags or {})
            if selected_plan_code:
                flags["initial_plan_intent"] = selected_plan_code
                flags["initial_plan_billing_interval"] = billing_interval
            else:
                flags.pop("initial_plan_intent", None)
                flags.pop("initial_plan_billing_interval", None)
            tenant.feature_flags = flags
            await TenantRepository.save(db, tenant)
        await TenantAdminRepository.save(db, admin)

    @staticmethod
    async def _recover_concurrent_registration(
        db: AsyncSession,
        *,
        normalized_email: str,
        school_name: str,
        password: str,
        selected_plan_code: str | None,
        billing_interval: str,
    ) -> tuple[Tenant, TenantAdmin]:
        """Recover the registration that won a concurrent insert race."""

        try:
            tenant = await TenantRepository.get_by_email_including_deleted(
                db,
                normalized_email,
                lock=True,
            )
            admin = await TenantAdminRepository.get_by_email(
                db,
                normalized_email,
                lock=True,
            )
            if tenant is None or admin is None:
                raise ConflictException(
                    "Tenant registration could not be recovered. Please try again."
                )

            state = TenantService.get_email_registration_state(
                admin=admin,
                tenant=tenant,
            )
            if state != EmailRegistrationState.PENDING:
                raise ConflictException("This email is already registered. Please log in.")
            if tenant.school_name.strip().casefold() != school_name.casefold():
                raise ConflictException(
                    "A pending registration already exists for this email "
                    "under a different school name."
                )

            admin = TenantRegistrationService._require_replaceable_pending_admin(admin=admin)
            await TenantRegistrationService._replace_pending_password(
                db,
                admin=admin,
                password=password,
                selected_plan_code=selected_plan_code,
                billing_interval=billing_interval,
            )
            await TenantService._ensure_tenant_admin_identity(
                db=db,
                admin=admin,
            )
            await db.commit()
            return tenant, admin
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def register_tenant(
        db: AsyncSession,
        payload: TenantRegisterRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, object]:
        """Register a tenant or update the password on a pending registration."""

        school_name = _normalize_school_name(payload.school_name)
        normalized_email = _normalize_email(str(payload.email))
        selected_plan_code = (
            payload.initial_plan_intent.value if payload.initial_plan_intent else None
        )
        billing_interval = "term"
        tenant: Tenant | None = None
        reused_pending_account = False

        try:
            await AccountEmailGuard.ensure_not_superadmin_email(
                db=db,
                email=normalized_email,
            )

            existing_tenant_by_name = await TenantRepository.get_by_school_name(
                db,
                school_name,
                lock=True,
            )
            existing_admin = await TenantAdminRepository.get_by_email(
                db,
                normalized_email,
                lock=True,
            )
            existing_tenant_by_email = await TenantRepository.get_by_email_including_deleted(
                db,
                normalized_email,
                lock=True,
            )

            if existing_tenant_by_name is not None:
                if (
                    existing_tenant_by_email is None
                    or existing_tenant_by_name.id != existing_tenant_by_email.id
                ):
                    raise ConflictException("This school name is already registered.")

            state = TenantService.get_email_registration_state(
                admin=existing_admin,
                tenant=existing_tenant_by_email,
            )
            if state == EmailRegistrationState.DELETED:
                raise ConflictException(
                    "This email belongs to a deleted school account. Please contact support."
                )
            if state == EmailRegistrationState.ACTIVE:
                raise ConflictException("This email is already registered. Please log in.")
            if state == EmailRegistrationState.REJECTED:
                raise ConflictException("This registration was rejected. Please contact support.")

            if state == EmailRegistrationState.PENDING:
                if existing_tenant_by_email is None:
                    raise ConflictException(
                        "This email is already registered. Please contact support."
                    )
                if (
                    existing_tenant_by_email.school_name.strip().casefold()
                    != school_name.casefold()
                ):
                    raise ConflictException(
                        "A pending registration already exists for this email "
                        "under a different school name."
                    )

                existing_admin = TenantRegistrationService._require_replaceable_pending_admin(
                    admin=existing_admin,
                )
                await TenantRegistrationService._replace_pending_password(
                    db,
                    admin=existing_admin,
                    password=payload.password,
                    selected_plan_code=selected_plan_code,
                    billing_interval=billing_interval,
                )
                await TenantService._ensure_tenant_admin_identity(
                    db=db,
                    admin=existing_admin,
                )
                tenant = existing_tenant_by_email
                reused_pending_account = True
            else:
                slug = await TenantService._unique_slug(db, school_name)
                tenant = Tenant(
                    school_name=school_name,
                    slug=slug,
                    email=normalized_email,
                    admission_number_prefix=None,
                    onboarding_completed=False,
                    verification_status=(TenantVerificationStatus.PENDING_VERIFICATION),
                    initial_plan_intent=payload.initial_plan_intent,
                    feature_flags=(
                        {
                            "initial_plan_intent": selected_plan_code,
                            "initial_plan_billing_interval": billing_interval,
                        }
                        if selected_plan_code
                        else {}
                    ),
                )
                await TenantRepository.create(db, tenant)
                await db.flush()
                await TenantAdminService.create_tenant_admin(
                    db=db,
                    tenant_id=tenant.id,
                    payload=TenantAdminCreate(
                        email=normalized_email,
                        password=payload.password,
                    ),
                )
            await db.commit()
        except IntegrityError:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)
            tenant, _admin = await TenantRegistrationService._recover_concurrent_registration(
                db,
                normalized_email=normalized_email,
                school_name=school_name,
                password=payload.password,
                selected_plan_code=selected_plan_code,
                billing_interval=billing_interval,
            )
            reused_pending_account = True
            logger.info(
                "Recovered concurrent tenant registration",
                extra={
                    "tenant_id": str(tenant.id),
                    "email": normalized_email,
                },
            )
        except Exception:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)
            raise

        await AuthIdentityService.invalidate_after_commit(db)
        if tenant is None:
            raise ConflictException("Tenant registration could not be completed.")

        resend_otp_available = True
        message = (
            "Registration successful. Please check your email for the verification code."
            if not reused_pending_account
            else ("Your pending registration was updated. We sent you a new verification code.")
        )

        try:
            await OTPService.generate_otp(
                db,
                RequestOTP(
                    email=normalized_email,
                    purpose=AuthPurpose.VERIFICATION.value,
                ),
                background_tasks=background_tasks,
            )
        except TooManyRequestsException:
            resend_otp_available = False
            message = (
                "Your registration is pending verification. "
                "A verification code was sent recently. Please use the latest "
                "code or wait before requesting another one."
            )

        await db.refresh(tenant)

        if reused_pending_account:
            return {
                "created": False,
                "email": tenant.email,
                "detail": message,
                "message": message,
                "verification_required": True,
                "purpose": AuthPurpose.VERIFICATION.value,
                "redirect_to": "/verify-otp",
                "resend_otp_available": resend_otp_available,
            }

        return {
            "created": True,
            "id": tenant.id,
            "school_name": tenant.school_name,
            "slug": tenant.slug,
            "admission_number_prefix": tenant.admission_number_prefix,
            "email": tenant.email,
            "status": tenant.status,
            "plan": tenant.plan,
            "timezone": tenant.timezone,
            "language": tenant.language,
            "onboarding_completed": tenant.onboarding_completed,
            "verification_status": tenant.verification_status,
            "created_at": tenant.created_at,
            "updated_at": tenant.updated_at,
            "detail": message,
            "message": message,
            "verification_required": True,
            "purpose": AuthPurpose.VERIFICATION.value,
            "redirect_to": "/verify-otp",
            "resend_otp_available": resend_otp_available,
        }
