from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics.models import AcademicTerm, AcademicTermStatus
from app.modules.subscriptions.cache import invalidate_tenant_subscription_cache
from app.modules.subscriptions.models import PaymentTransaction, TermPlanEntitlement
from app.modules.subscriptions.plans import get_plan_entitlements
from app.modules.subscriptions.providers.paystack import PaystackClient
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import SubscriptionCheckoutResponse
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    PaymentStatus,
    TermEntitlementStatus,
)
from app.tenant_management.models import SubscriptionPlan

TERM_SAFETY_LIFETIME_DAYS = 214
PENDING_CHECKOUT_TTL = timedelta(minutes=30)
PAID_TERM_PLANS = {
    SubscriptionPlan.PLUS,
    SubscriptionPlan.PROFESSIONAL,
    SubscriptionPlan.ENTERPRISE,
}
PLAN_RANK = {
    SubscriptionPlan.FREE: 0,
    SubscriptionPlan.PLUS: 1,
    SubscriptionPlan.PROFESSIONAL: 2,
    SubscriptionPlan.ENTERPRISE: 3,
}


class TermPlanEntitlementService:
    @staticmethod
    async def _term(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID, *, lock: bool = False
    ) -> AcademicTerm:
        query = select(AcademicTerm).where(
            AcademicTerm.id == term_id,
            AcademicTerm.tenant_id == tenant_id,
        )
        if lock:
            query = query.with_for_update()
        term = (await db.execute(query)).scalar_one_or_none()
        if term is None:
            raise NotFoundException("Academic term not found.")
        return term

    @staticmethod
    async def get_active(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID, *, lock: bool = False
    ) -> TermPlanEntitlement | None:
        query = (
            select(TermPlanEntitlement)
            .where(
                TermPlanEntitlement.tenant_id == tenant_id,
                TermPlanEntitlement.academic_term_id == term_id,
                TermPlanEntitlement.status == TermEntitlementStatus.ACTIVE,
            )
            .order_by(TermPlanEntitlement.activated_at.desc())
            .limit(1)
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def _get_entitlement_for_transaction(
        db: AsyncSession,
        transaction_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> TermPlanEntitlement | None:
        query = (
            select(TermPlanEntitlement)
            .where(TermPlanEntitlement.payment_transaction_id == transaction_id)
            .limit(1)
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def _get_pending_checkout(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> PaymentTransaction | None:
        query = (
            select(PaymentTransaction)
            .where(
                PaymentTransaction.tenant_id == tenant_id,
                PaymentTransaction.academic_term_id == term_id,
                PaymentTransaction.provider == PaymentProvider.PAYSTACK,
                PaymentTransaction.status == PaymentStatus.PENDING,
            )
            .order_by(PaymentTransaction.created_at.desc())
            .limit(1)
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    def _pending_checkout_is_stale(
        transaction: PaymentTransaction,
        *,
        as_of: datetime | None = None,
    ) -> bool:
        now = as_of or datetime.now(timezone.utc)
        return (
            transaction.status == PaymentStatus.PENDING
            and transaction.created_at is not None
            and transaction.created_at < now - PENDING_CHECKOUT_TTL
        )

    @staticmethod
    async def expire_stale_pending_checkouts(
        db: AsyncSession,
        *,
        as_of: datetime | None = None,
        tenant_id: uuid.UUID | None = None,
        term_id: uuid.UUID | None = None,
    ) -> int:
        now = as_of or datetime.now(timezone.utc)
        query = select(PaymentTransaction).where(
            PaymentTransaction.provider == PaymentProvider.PAYSTACK,
            PaymentTransaction.status == PaymentStatus.PENDING,
            PaymentTransaction.created_at < now - PENDING_CHECKOUT_TTL,
        )
        if tenant_id is not None:
            query = query.where(PaymentTransaction.tenant_id == tenant_id)
        if term_id is not None:
            query = query.where(PaymentTransaction.academic_term_id == term_id)
        rows = list((await db.execute(query.with_for_update())).scalars().all())
        for transaction in rows:
            transaction.status = PaymentStatus.ABANDONED
            transaction.failure_reason = "Pending checkout expired before payment completion."
        if rows:
            await db.flush()
        return len(rows)

    @staticmethod
    def amount_kobo(plan: SubscriptionPlan) -> int:
        fields = {
            SubscriptionPlan.PLUS: "PAYSTACK_PLUS_TERM_AMOUNT_KOBO",
            SubscriptionPlan.PROFESSIONAL: "PAYSTACK_PROFESSIONAL_TERM_AMOUNT_KOBO",
            SubscriptionPlan.ENTERPRISE: "PAYSTACK_ENTERPRISE_TERM_AMOUNT_KOBO",
        }
        if plan not in fields:
            return 0
        return int(getattr(settings, fields[plan]))

    @staticmethod
    def _ensure_paid_checkout_term_state(term: AcademicTerm) -> None:
        if term.status not in {AcademicTermStatus.DRAFT, AcademicTermStatus.OPEN}:
            raise ConflictException(
                "Only a draft or open academic term can start a paid-plan checkout."
            )

    @staticmethod
    def _ensure_paid_settlement_term_state(term: AcademicTerm) -> None:
        if term.status not in {
            AcademicTermStatus.DRAFT,
            AcademicTermStatus.OPEN,
            AcademicTermStatus.CLOSING,
        }:
            raise ConflictException(
                "A paid term transaction cannot be activated after the academic term is closed."
            )

    @staticmethod
    def _ensure_paid_transition(
        existing: TermPlanEntitlement | None,
        target_plan: SubscriptionPlan,
    ) -> None:
        if existing is None or existing.plan_code == SubscriptionPlan.FREE:
            return
        if existing.plan_code not in PAID_TERM_PLANS:
            raise ConflictException("The current term plan cannot be replaced by this checkout.")
        if PLAN_RANK[target_plan] <= PLAN_RANK[existing.plan_code]:
            raise ConflictException(
                "An active term can only move to a higher paid plan. "
                "Choose a lower plan when activating the next academic term."
            )

    @staticmethod
    def _checkout_response(transaction: PaymentTransaction) -> SubscriptionCheckoutResponse:
        return SubscriptionCheckoutResponse(
            reference=transaction.reference,
            authorization_url=transaction.authorization_url or "",
            access_code=transaction.access_code or "",
            amount=transaction.amount,
            amount_kobo=transaction.amount_kobo,
            currency=transaction.currency,
            plan_code=transaction.plan_code.value,
            billing_interval=BillingInterval.TERM,
        )

    @staticmethod
    async def ensure_open_eligible(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID
    ) -> TermPlanEntitlement:
        entitlement = await TermPlanEntitlementService.get_active(db, tenant_id, term_id, lock=True)
        now = datetime.now(timezone.utc)
        if entitlement is None or (
            entitlement.safety_expires_at and entitlement.safety_expires_at <= now
        ):
            tenant = await SubscriptionRepository.get_tenant(db, tenant_id)
            suggested = getattr(tenant, "initial_plan_intent", None) or SubscriptionPlan.FREE
            raise ConflictException(
                "Activate a plan for this academic term before opening it.",
                payload={
                    "code": "TERM_PLAN_ACTIVATION_REQUIRED",
                    "term_id": str(term_id),
                    "suggested_plan": suggested.value,
                    "payment_required": suggested
                    not in {SubscriptionPlan.FREE, SubscriptionPlan.FREE_TRIAL},
                    "amount_kobo": TermPlanEntitlementService.amount_kobo(suggested),
                },
            )
        return entitlement

    @staticmethod
    async def activate_free(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        admin_id: uuid.UUID | None,
    ) -> TermPlanEntitlement:
        term = await TermPlanEntitlementService._term(db, tenant_id, term_id, lock=True)
        if term.status != AcademicTermStatus.DRAFT:
            raise ConflictException(
                "The Free plan can only be activated while the academic term is still a draft."
            )
        existing = await TermPlanEntitlementService.get_active(db, tenant_id, term_id, lock=True)
        if existing:
            if existing.plan_code == SubscriptionPlan.FREE:
                return existing
            raise ConflictException("This term already has an active paid entitlement.")

        usage = await SubscriptionRepository.get_all_resource_usage(db, tenant_id)
        limits = get_plan_entitlements(SubscriptionPlan.FREE).limits
        blockers = [
            {"resource": resource.value, "used": used, "limit": limits[resource]}
            for resource, used in usage.items()
            if limits[resource] is not None and used > limits[resource]
        ]
        if blockers:
            raise ConflictException(
                "Current school usage exceeds Free plan limits.",
                payload={"code": "FREE_PLAN_LIMITS_EXCEEDED", "blockers": blockers},
            )

        now = datetime.now(timezone.utc)
        entitlement = TermPlanEntitlement(
            tenant_id=tenant_id,
            academic_term_id=term_id,
            plan_code=SubscriptionPlan.FREE,
            status=TermEntitlementStatus.ACTIVE,
            amount=Decimal("0"),
            currency="NGN",
            provider=PaymentProvider.MANUAL,
            activated_at=now,
            safety_expires_at=now + timedelta(days=TERM_SAFETY_LIFETIME_DAYS),
            activated_by_admin_id=admin_id,
        )
        db.add(entitlement)
        tenant = await SubscriptionRepository.get_tenant(db, tenant_id)
        if tenant:
            tenant.initial_plan_intent = None
            tenant.plan = SubscriptionPlan.FREE
        await db.flush()
        await db.commit()
        await invalidate_tenant_subscription_cache(tenant_id)
        return entitlement

    @staticmethod
    async def initialize_paid_checkout(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        plan: SubscriptionPlan,
        email: str,
    ) -> SubscriptionCheckoutResponse:
        if plan not in PAID_TERM_PLANS:
            raise ConflictException("Select Plus, Professional, or Enterprise for paid activation.")

        term = await TermPlanEntitlementService._term(db, tenant_id, term_id, lock=True)
        TermPlanEntitlementService._ensure_paid_checkout_term_state(term)

        existing_entitlement = await TermPlanEntitlementService.get_active(
            db, tenant_id, term_id, lock=True
        )
        TermPlanEntitlementService._ensure_paid_transition(existing_entitlement, plan)

        pending = await TermPlanEntitlementService._get_pending_checkout(
            db, tenant_id, term_id, lock=True
        )
        if pending is not None:
            now = datetime.now(timezone.utc)
            reusable = bool(pending.authorization_url) and (
                pending.created_at is None or pending.created_at >= now - PENDING_CHECKOUT_TTL
            )
            if reusable:
                if pending.plan_code != plan:
                    raise ConflictException(
                        "A different term-plan checkout is already in progress. "
                        "Finish or wait for that checkout to expire before choosing another plan."
                    )
                return TermPlanEntitlementService._checkout_response(pending)

            pending.status = PaymentStatus.ABANDONED
            pending.failure_reason = "Pending checkout expired before payment completion."

        amount_kobo = TermPlanEntitlementService.amount_kobo(plan)
        if amount_kobo <= 0:
            raise ConflictException(
                "Paid term pricing is not configured correctly for the selected plan."
            )

        callback_url = str(settings.PAYSTACK_CALLBACK_URL or "").strip()
        if settings.is_production_like and not callback_url:
            raise ConflictException("Paystack callback URL is not configured for this environment.")

        reference = f"term-{term_id.hex[:12]}-{uuid.uuid4().hex[:16]}"
        transaction = PaymentTransaction(
            tenant_id=tenant_id,
            academic_term_id=term_id,
            provider=PaymentProvider.PAYSTACK,
            status=PaymentStatus.PENDING,
            reference=reference,
            plan_code=plan,
            billing_interval=BillingInterval.TERM,
            amount=Decimal(amount_kobo) / 100,
            amount_kobo=amount_kobo,
            currency="NGN",
        )
        db.add(transaction)
        await db.flush()

        response = await PaystackClient().initialize_transaction(
            email=email,
            amount_kobo=amount_kobo,
            reference=reference,
            callback_url=callback_url,
            metadata={
                "tenant_id": str(tenant_id),
                "academic_term_id": str(term_id),
                "plan_code": plan.value,
                "amount_kobo": amount_kobo,
            },
        )
        data = response.get("data") or {}
        transaction.authorization_url = data.get("authorization_url")
        transaction.access_code = data.get("access_code")
        if not transaction.authorization_url or not transaction.access_code:
            raise ConflictException("Paystack did not return a usable checkout session.")

        await db.commit()
        return TermPlanEntitlementService._checkout_response(transaction)

    @staticmethod
    async def activate_verified_transaction(
        db: AsyncSession,
        transaction: PaymentTransaction,
        provider_data: dict,
        *,
        commit: bool = True,
    ) -> TermPlanEntitlement:
        if transaction.academic_term_id is None:
            raise ConflictException("Payment is not attached to an academic term.")

        data = provider_data.get("data") or provider_data
        if (
            data.get("status") != "success"
            or int(data.get("amount") or -1) != transaction.amount_kobo
            or data.get("currency") != transaction.currency
        ):
            raise ConflictException(
                "Paystack verification did not match the expected term payment."
            )

        metadata = data.get("metadata") or {}
        if (
            str(metadata.get("tenant_id")) != str(transaction.tenant_id)
            or str(metadata.get("academic_term_id")) != str(transaction.academic_term_id)
            or str(metadata.get("plan_code")) != transaction.plan_code.value
        ):
            raise ConflictException(
                "Paystack term payment metadata did not match the expected purchase."
            )

        already_activated = await TermPlanEntitlementService._get_entitlement_for_transaction(
            db, transaction.id, lock=True
        )
        if already_activated is not None:
            return already_activated

        term = await TermPlanEntitlementService._term(
            db,
            transaction.tenant_id,
            transaction.academic_term_id,
            lock=True,
        )
        TermPlanEntitlementService._ensure_paid_settlement_term_state(term)

        existing = await TermPlanEntitlementService.get_active(
            db,
            transaction.tenant_id,
            transaction.academic_term_id,
            lock=True,
        )
        TermPlanEntitlementService._ensure_paid_transition(existing, transaction.plan_code)

        now = datetime.now(timezone.utc)
        if existing:
            existing.status = TermEntitlementStatus.CLOSED
            existing.closed_at = now
            existing.closed_reason = "mid_term_upgrade"

        transaction.status = PaymentStatus.SUCCESS
        transaction.paid_at = now
        transaction.provider_transaction_id = (
            str(data.get("id"))
            if data.get("id") is not None
            else transaction.provider_transaction_id
        )
        transaction.raw_payload = data

        entitlement = TermPlanEntitlement(
            tenant_id=transaction.tenant_id,
            academic_term_id=transaction.academic_term_id,
            plan_code=transaction.plan_code,
            status=TermEntitlementStatus.ACTIVE,
            payment_transaction_id=transaction.id,
            amount=transaction.amount,
            currency=transaction.currency,
            provider=PaymentProvider.PAYSTACK,
            activated_at=now,
            safety_expires_at=now + timedelta(days=TERM_SAFETY_LIFETIME_DAYS),
        )
        db.add(entitlement)

        tenant = await SubscriptionRepository.get_tenant(db, transaction.tenant_id)
        if tenant:
            tenant.plan = transaction.plan_code
            tenant.initial_plan_intent = None

        await db.flush()
        if commit:
            await db.commit()
            await invalidate_tenant_subscription_cache(transaction.tenant_id)
        return entitlement

    @staticmethod
    async def close_for_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        *,
        reason: str = "term_closed",
    ) -> None:
        await TermPlanEntitlementService.expire_stale_pending_checkouts(
            db,
            tenant_id=tenant_id,
            term_id=term_id,
        )
        pending = await TermPlanEntitlementService._get_pending_checkout(
            db, tenant_id, term_id, lock=True
        )
        if pending is not None:
            raise ConflictException(
                "This academic term still has a pending Paystack checkout. "
                "Complete the payment or wait for the checkout to expire before finalizing closure."
            )

        entitlement = await TermPlanEntitlementService.get_active(db, tenant_id, term_id, lock=True)
        if entitlement:
            entitlement.status = TermEntitlementStatus.CLOSED
            entitlement.closed_at = datetime.now(timezone.utc)
            entitlement.closed_reason = reason

    @staticmethod
    async def reconcile(db: AsyncSession, *, as_of: datetime | None = None) -> dict[str, int]:
        """Safety repair only; normal entitlement closure is synchronous with term closure."""
        now = as_of or datetime.now(timezone.utc)
        await TermPlanEntitlementService.expire_stale_pending_checkouts(
            db,
            as_of=now,
        )
        result = await db.execute(
            select(TermPlanEntitlement, AcademicTerm.status)
            .join(AcademicTerm, AcademicTerm.id == TermPlanEntitlement.academic_term_id)
            .where(
                TermPlanEntitlement.status == TermEntitlementStatus.ACTIVE,
                or_(
                    AcademicTerm.status == AcademicTermStatus.CLOSED,
                    TermPlanEntitlement.safety_expires_at <= now,
                ),
            )
            .with_for_update()
        )
        repaired_closed = 0
        safety_expired = 0
        tenant_ids: set[uuid.UUID] = set()
        for entitlement, term_status in result.all():
            tenant_ids.add(entitlement.tenant_id)
            if term_status == AcademicTermStatus.CLOSED:
                entitlement.status = TermEntitlementStatus.CLOSED
                entitlement.closed_at = now
                entitlement.closed_reason = "reconciled_closed_term"
                repaired_closed += 1
            else:
                entitlement.status = TermEntitlementStatus.EXPIRED
                entitlement.expired_at = now
                entitlement.closed_reason = "safety_cap_reached"
                safety_expired += 1
        await db.commit()
        for tenant_id in tenant_ids:
            await invalidate_tenant_subscription_cache(tenant_id)
        return {"closed_term_repaired": repaired_closed, "safety_expired": safety_expired}
