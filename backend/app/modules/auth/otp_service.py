"""OTP verification, password-reset tokens, and tenant activation."""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import (
    hash_auth_secret,
    hash_otp,
    hash_password,
    verify_auth_secret,
    verify_otp as verify_otp_hash,
)
from app.config.settings import settings
from app.core.email.enums import EmailCategory
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    TooManyRequestsException,
)
from app.core.utils.email import send_email
from app.core.utils.email_templates import get_otp_email_html
from app.core.utils.otp_rate_limiter import OTPRateLimiter
from app.modules.auth.login_service import AuthService
from app.modules.auth.models import AuthPurpose, AuthRecord
from app.modules.auth.schemas import TenantActivationRequest, VerifyOTP
from app.modules.parents.models import ParentAccount, ParentAccountStatus
from app.modules.teachers.models import TeacherAccount, TeacherAccountStatus
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.tenant_management.models import TenantStatus, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(value: str) -> str:
    return value.strip().casefold()


class OTPService:
    """Create and consume email OTP records."""

    @staticmethod
    async def generate_otp(
        db: AsyncSession,
        payload,
        *,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, str]:
        email = _normalize_email(str(payload.email))
        purpose = AuthPurpose(payload.purpose)
        actor, resolution = await AuthService.resolve_email_owner(db, email=email)

        if purpose == AuthPurpose.VERIFICATION:
            if getattr(actor, "is_verified", False):
                raise ConflictException("Account is already verified.")
        elif purpose == AuthPurpose.PASSWORD_RESET:
            if not getattr(actor, "is_active", False) or not getattr(actor, "is_verified", False):
                raise BadRequestException("Account is not eligible for password reset.")
        else:
            raise BadRequestException("Unsupported OTP purpose.")

        allowed, retry_after = OTPRateLimiter().is_allowed(email, purpose.value)
        if not allowed:
            raise TooManyRequestsException(
                detail=f"A code was sent recently. Try again in {retry_after} seconds."
            )

        code = "".join(random.choice(string.digits) for _ in range(6))
        expires_at = _utc_now() + timedelta(minutes=settings.OTP_EXPIRATION_MINUTES)
        await db.execute(
            delete(AuthRecord).where(
                AuthRecord.email == email,
                AuthRecord.purpose == purpose,
                AuthRecord.is_used.is_(False),
            )
        )
        db.add(
            AuthRecord(
                tenant_id=resolution.tenant_id,
                email=email,
                hashed_value=hash_otp(code),
                purpose=purpose,
                expires_at=expires_at,
                is_used=False,
            )
        )
        await db.commit()

        html = get_otp_email_html(code, purpose.value, settings.OTP_EXPIRATION_MINUTES)
        email_tags = (("email_type", "otp"), ("purpose", purpose.value))

        if background_tasks is not None:
            background_tasks.add_task(
                send_email,
                email,
                "Your Weave verification code",
                html,
                True,
                category=EmailCategory.SECURITY,
                tags=email_tags,
            )
        else:
            await send_email(
                email,
                "Your Weave verification code",
                html,
                True,
                category=EmailCategory.SECURITY,
                tags=email_tags,
            )
        return {"detail": "OTP sent successfully."}

    @staticmethod
    async def verify_otp(db: AsyncSession, payload: VerifyOTP) -> dict[str, str]:
        email = _normalize_email(str(payload.email))
        purpose = AuthPurpose(payload.purpose)
        now = _utc_now()
        record = (
            await db.execute(
                select(AuthRecord)
                .where(
                    AuthRecord.email == email,
                    AuthRecord.purpose == purpose,
                    AuthRecord.is_used.is_(False),
                    AuthRecord.expires_at > now,
                )
                .order_by(AuthRecord.created_at.desc())
                .with_for_update()
                .limit(1)
            )
        ).scalar_one_or_none()
        if record is None or not verify_otp_hash(payload.code, record.hashed_value):
            raise BadRequestException("Invalid OTP")

        actor, resolution = await AuthService.resolve_email_owner(
            db,
            email=email,
            lock=True,
        )
        record.is_used = True
        db.add(record)

        if purpose == AuthPurpose.VERIFICATION:
            actor.is_verified = True
            actor.is_active = True
            if isinstance(actor, TenantAdmin):
                actor.account_status = TenantAdminStatus.ACTIVE
                tenant = await TenantRepository.get_by_id(db, actor.tenant_id, lock=True)
                if tenant is not None:
                    tenant.verification_status = TenantVerificationStatus.ACTIVE
                    if tenant.status == TenantStatus.INACTIVE:
                        tenant.status = TenantStatus.TRIAL
                    db.add(tenant)
            elif isinstance(actor, ParentAccount):
                actor.account_status = ParentAccountStatus.ACTIVE
            elif isinstance(actor, TeacherAccount):
                actor.account_status = TeacherAccountStatus.ACTIVE
            db.add(actor)
            await db.commit()
            return {"detail": "Account verified successfully."}

        import secrets

        raw_reset_token = secrets.token_urlsafe(48)
        db.add(
            AuthRecord(
                tenant_id=resolution.tenant_id,
                email=email,
                hashed_value=hash_auth_secret(raw_reset_token),
                purpose=AuthPurpose.PASSWORD_RESET,
                expires_at=now + timedelta(minutes=15),
                is_used=False,
            )
        )
        await db.commit()
        return {
            "detail": "OTP verified successfully.",
            "reset_token": raw_reset_token,
        }


class TenantActivationService:
    """Activate an invited tenant administrator."""

    @staticmethod
    async def activate_tenant(
        db: AsyncSession,
        payload: TenantActivationRequest,
    ) -> dict[str, str]:
        email = _normalize_email(str(payload.email))
        now = _utc_now()
        records = (
            await db.execute(
                select(AuthRecord)
                .where(
                    AuthRecord.email == email,
                    AuthRecord.purpose == AuthPurpose.TENANT_ACTIVATION,
                    AuthRecord.is_used.is_(False),
                    AuthRecord.expires_at > now,
                )
                .order_by(AuthRecord.created_at.desc())
                .with_for_update()
            )
        ).scalars().all()
        record = next(
            (item for item in records if verify_auth_secret(payload.token, item.hashed_value)),
            None,
        )
        if record is None:
            raise BadRequestException("Tenant activation token is invalid or expired.")

        admin = await TenantAdminRepository.get_by_email(db, email, lock=True)
        if admin is None:
            raise NotFoundException("Tenant administrator not found.")
        tenant = await TenantRepository.get_by_id(db, admin.tenant_id, lock=True)
        if tenant is None:
            raise NotFoundException("Tenant not found.")

        admin.password_hash = hash_password(payload.password)
        admin.account_status = TenantAdminStatus.ACTIVE
        admin.is_verified = True
        admin.is_active = True
        tenant.verification_status = TenantVerificationStatus.ACTIVE
        tenant.status = TenantStatus.TRIAL
        record.is_used = True
        db.add(admin)
        db.add(tenant)
        db.add(record)
        await db.commit()
        return {"detail": "Tenant activated successfully."}
