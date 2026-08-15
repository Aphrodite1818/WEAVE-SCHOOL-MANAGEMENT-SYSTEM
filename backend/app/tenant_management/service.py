# ====================================== #
#     tenant_management/service.py       #
# ====================================== #

"""Implement the tenant management service layer."""

import uuid
from enum import StrEnum

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.security import verify_password
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    TooManyRequestsException,
)
from app.core.utils.validators import generate_slug
from app.modules.auth.account_email_guard import AccountEmailGuard
from app.modules.auth.models import AuthPurpose
from app.modules.auth.schemas import RequestOTP
from app.modules.auth.service import OTPService
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.modules.tenant_admins.schemas import TenantAdminCreate
from app.modules.tenant_admins.service import TenantAdminService
from app.tenant_management.models import Tenant, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository
from app.tenant_management.schemas import (
    TenantOnboardingStatusResponse,
    TenantOnboardingUpdate,
    TenantRegisterRequest,
    TenantUpdate,
)

logger = get_logger(__name__)


class EmailRegistrationState(StrEnum):
    """Container for tenant management state."""

    AVAILABLE = "AVAILABLE"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    DELETED = "DELETED"


def _normalize_email(email: str) -> str:
    """Normalize the email address."""

    return email.strip().lower()


def _normalize_school_name(school_name: str) -> str:
    """Normalize the school name."""

    return school_name.strip()


def _normalize_admission_number_prefix(prefix: str | None) -> str | None:
    """Normalize the tenant admission number prefix."""

    if prefix is None:
        return None

    cleaned_prefix = prefix.strip().upper()
    return cleaned_prefix or None


def _is_tenant_onboarding_complete(
    *,
    school_name: str | None,
    email: str | None,
    admission_number_prefix: str | None,
    institution_type: object | None,
    address: str | None,
    city: str | None,
    state: str | None,
) -> bool:
    """Return whether the tenant has enough data to complete school onboarding."""

    return bool(
        school_name
        and school_name.strip()
        and email
        and email.strip()
        and admission_number_prefix
        and admission_number_prefix.strip()
        and institution_type is not None
        and address
        and address.strip()
        and city
        and city.strip()
        and state
        and state.strip()
    )


class TenantService:
    """Business logic for the tenant management domain."""

    ONBOARDING_REQUIRED_FIELDS = [
        "admission_number_prefix",
        "institution_type",
        "address",
        "city",
        "state",
    ]

    @staticmethod
    def get_email_registration_state(
        admin: TenantAdmin | None,
        tenant: Tenant | None,
    ) -> EmailRegistrationState:
        """
        Decide how tenant registration should treat an email.

        AVAILABLE:
            No tenant admin or tenant owns this email yet.

        PENDING:
            A tenant admin or tenant exists but has not completed verification.

        ACTIVE:
            A tenant admin or tenant already owns this email.

        REJECTED:
            A tenant registration exists but was rejected.

        DELETED:
            A deleted tenant still owns this email.
        """

        if tenant is not None and tenant.is_deleted:
            return EmailRegistrationState.DELETED

        if tenant is not None and tenant.verification_status == TenantVerificationStatus.REJECTED:
            return EmailRegistrationState.REJECTED

        if admin is None and tenant is None:
            return EmailRegistrationState.AVAILABLE

        if admin is not None and admin.account_status == TenantAdminStatus.PENDING:
            return EmailRegistrationState.PENDING

        if (
            tenant is not None
            and tenant.verification_status == TenantVerificationStatus.PENDING_VERIFICATION
        ):
            return EmailRegistrationState.PENDING

        return EmailRegistrationState.ACTIVE

    @staticmethod
    async def _unique_slug(db: AsyncSession, school_name: str) -> str:
        """Generate a unique tenant slug from the school name."""

        base_slug = generate_slug(school_name)
        slug = base_slug
        counter = 1

        while await TenantRepository.slug_exists(db, slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    @staticmethod
    async def _ensure_tenant_admin_identity(
        db: AsyncSession,
        *,
        admin: TenantAdmin,
    ) -> None:
        """Create or repair the tenant-admin identity for registration retries."""

        await AuthIdentityService.ensure_for_actor(
            db=db,
            tenant_id=admin.tenant_id,
            payload=AuthIdentityCreate(
                identifier=admin.email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.TENANT_ADMIN,
                actor_id=admin.id,
                is_active=True,
            ),
        )

    @staticmethod
    async def _recover_concurrent_registration(
        *,
        db: AsyncSession,
        normalized_email: str,
        school_name: str,
    ) -> tuple[Tenant, TenantAdmin]:
        """Recover the pending registration that won a concurrent insert race.

        The losing request may reuse the winning pending registration only when
        both requests refer to the same workspace email and school. It must not
        replace the password chosen by the winning request.
        """

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
    async def _unique_slug_for_tenant(
        db: AsyncSession,
        school_name: str,
        tenant_id: uuid.UUID,
    ) -> str:
        """Generate a unique slug while allowing a tenant to retain its slug."""

        base_slug = generate_slug(school_name)
        slug = base_slug
        counter = 1

        while True:
            existing_tenant = await TenantRepository.get_by_slug(db, slug)

            if existing_tenant is None or existing_tenant.id == tenant_id:
                return slug

            slug = f"{base_slug}-{counter}"
            counter += 1

    @staticmethod
    async def register_tenant(
        db: AsyncSession,
        payload: TenantRegisterRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict:
        """Register a school tenant and its initial tenant administrator."""

        school_name = _normalize_school_name(payload.school_name)
        normalized_email = _normalize_email(str(payload.email))

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
                if existing_tenant_by_email is None:
                    raise ConflictException("This school name is already registered.")

                if existing_tenant_by_name.id != existing_tenant_by_email.id:
                    raise ConflictException("This school name is already registered.")

            email_state = TenantService.get_email_registration_state(
                admin=existing_admin,
                tenant=existing_tenant_by_email,
            )

            if email_state == EmailRegistrationState.DELETED:
                raise ConflictException(
                    "This email belongs to a deleted school account. Please contact support."
                )

            if email_state == EmailRegistrationState.ACTIVE:
                raise ConflictException("This email is already registered. Please log in.")

            if email_state == EmailRegistrationState.REJECTED:
                raise ConflictException("This registration was rejected. Please contact support.")

            if email_state == EmailRegistrationState.PENDING:
                if existing_admin is None or existing_tenant_by_email is None:
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

                if not verify_password(
                    payload.password,
                    existing_admin.password_hash,
                ):
                    raise ConflictException(
                        "A pending registration already exists for this email. "
                        "The password does not match the original registration. "
                        "Use the original password or verify the email and reset it."
                    )

                tenant = existing_tenant_by_email
                reused_pending_account = True

                await TenantService._ensure_tenant_admin_identity(
                    db=db,
                    admin=existing_admin,
                )

                logger.info(
                    "Tenant registration reused existing pending account",
                    extra={
                        "tenant_id": str(tenant.id),
                        "email": normalized_email,
                    },
                )
            else:
                slug = await TenantService._unique_slug(db, school_name)

                tenant = Tenant(
                    school_name=school_name,
                    slug=slug,
                    email=normalized_email,
                    admission_number_prefix=None,
                    onboarding_completed=False,
                    verification_status=(TenantVerificationStatus.PENDING_VERIFICATION),
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

                logger.info(
                    "Tenant and tenant admin created during registration",
                    extra={
                        "tenant_id": str(tenant.id),
                        "email": normalized_email,
                        "actor_type": "tenant_admin",
                    },
                )
            await db.commit()
        except IntegrityError:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)

            tenant, _admin = await TenantService._recover_concurrent_registration(
                db=db,
                normalized_email=normalized_email,
                school_name=school_name,
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

        # The registration transaction has committed successfully here.
        await AuthIdentityService.invalidate_after_commit(db)

        if tenant is None:
            raise ConflictException("Tenant registration could not be completed")

        message = "Registration successful. Please check your email for the verification code."
        resend_otp_available = True

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
            if not reused_pending_account:
                raise

            resend_otp_available = False
            message = (
                "Your registration already exists but needs verification. "
                "A verification code was sent recently. Please use the latest "
                "code or wait before requesting another one."
            )

        await db.refresh(tenant)

        if reused_pending_account:
            if resend_otp_available:
                message = (
                    "Your registration already exists but needs verification. "
                    "We sent you a new verification code."
                )

            logger.info(
                "OTP resent for existing pending tenant registration",
                extra={
                    "tenant_id": str(tenant.id),
                    "email": normalized_email,
                },
            )

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

        logger.info(
            "OTP sent to newly registered tenant admin",
            extra={
                "tenant_id": str(tenant.id),
                "email": normalized_email,
            },
        )

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

    @staticmethod
    async def get_tenant_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> Tenant:
        """Return tenant by id."""

        tenant = await TenantRepository.get_by_id(db, tenant_id)

        if not tenant:
            raise NotFoundException("Tenant not found")

        return tenant

    @staticmethod
    async def update_tenant_profile(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TenantUpdate,
    ) -> Tenant:
        """Update tenant profile."""

        tenant = await TenantRepository.get_by_id(db, tenant_id)

        if not tenant:
            raise NotFoundException("Tenant not found")

        update_data = payload.model_dump(
            mode="json",
            exclude_unset=True,
        )

        if not update_data:
            return tenant

        school_name = update_data.get("school_name")

        if school_name is not None:
            normalized_school_name = school_name.strip()

            if not normalized_school_name:
                raise BadRequestException("school_name cannot be empty")

            existing_tenant = await TenantRepository.get_by_school_name(
                db,
                normalized_school_name,
            )

            if existing_tenant and existing_tenant.id != tenant_id:
                raise ConflictException("A school with this name already exists")

            update_data["school_name"] = normalized_school_name

            if normalized_school_name.casefold() != tenant.school_name.strip().casefold():
                update_data["slug"] = await TenantService._unique_slug_for_tenant(
                    db,
                    normalized_school_name,
                    tenant_id,
                )

        email = update_data.get("email")

        if email is not None:
            normalized_email = _normalize_email(email)

            if normalized_email != _normalize_email(tenant.email):
                raise BadRequestException(
                    "Tenant email cannot be changed from this endpoint because "
                    "it is tied to administrator onboarding."
                )

            update_data["email"] = normalized_email

        whatsapp_number = update_data.get("school_bot_whatssap_number")

        if whatsapp_number:
            existing = await TenantRepository.get_by_school_bot_number(
                db,
                whatsapp_number,
            )

            if existing and existing.id != tenant_id:
                raise ConflictException("This WhatsApp number is already in use by another school")

        admission_number_prefix = update_data.get("admission_number_prefix")

        if admission_number_prefix is not None:
            normalized_prefix = _normalize_admission_number_prefix(admission_number_prefix)
            update_data["admission_number_prefix"] = normalized_prefix

            if normalized_prefix is not None:
                existing = await TenantRepository.get_by_admission_number_prefix(
                    db,
                    normalized_prefix,
                )

                if existing and existing.id != tenant_id:
                    raise ConflictException("Prefix not available")

        institution_type = update_data.get("institution_type")
        if (
            institution_type is not None
            and tenant.institution_type is not None
            and institution_type != tenant.institution_type
        ):
            from app.modules.classes.repository import AcademicLevelRepository

            levels = await AcademicLevelRepository.list_for_tenant(
                db, tenant_id, include_archived=True
            )
            if levels:
                raise ConflictException(
                    "Clear the existing academic structure before changing institution type."
                )

        update_data["onboarding_completed"] = _is_tenant_onboarding_complete(
            school_name=update_data.get("school_name", tenant.school_name),
            email=update_data.get("email", tenant.email),
            admission_number_prefix=update_data.get(
                "admission_number_prefix",
                tenant.admission_number_prefix,
            ),
            institution_type=update_data.get("institution_type", tenant.institution_type),
            address=update_data.get("address", tenant.address),
            city=update_data.get("city", tenant.city),
            state=update_data.get("state", tenant.state),
        )

        for field, value in update_data.items():
            setattr(tenant, field, value)

        updated_tenant = await TenantRepository.save(db, tenant)

        await db.commit()
        await db.refresh(updated_tenant)

        return updated_tenant

    @staticmethod
    async def update_tenant_onboarding(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TenantOnboardingUpdate,
    ) -> Tenant:
        """Update the tenant onboarding fields."""

        return await TenantService.update_tenant_profile(
            db=db,
            tenant_id=tenant_id,
            payload=TenantUpdate(**payload.model_dump(mode="json")),
        )

    @staticmethod
    async def get_tenant_onboarding_status(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> TenantOnboardingStatusResponse:
        """Return tenant-admin onboarding status for the attached tenant."""

        tenant = await TenantService.get_tenant_by_id(
            db=db,
            tenant_id=tenant_id,
        )

        return TenantOnboardingStatusResponse(
            actor_type="tenant_admin",
            tenant_id=tenant.id,
            onboarding_required=not tenant.onboarding_completed,
            onboarding_completed=tenant.onboarding_completed,
            completion_target="tenant",
            required_fields=TenantService.ONBOARDING_REQUIRED_FIELDS,
            current_values={
                "school_name": tenant.school_name,
                "email": tenant.email,
                "admission_number_prefix": tenant.admission_number_prefix,
                "institution_type": tenant.institution_type,
                "phone": tenant.phone,
                "address": tenant.address,
                "city": tenant.city,
                "state": tenant.state,
                "country": tenant.country,
                "logo_url": tenant.logo_url,
                "timezone": tenant.timezone,
                "language": tenant.language,
                "school_bot_whatssap_number": tenant.school_bot_whatssap_number,
            },
        )
