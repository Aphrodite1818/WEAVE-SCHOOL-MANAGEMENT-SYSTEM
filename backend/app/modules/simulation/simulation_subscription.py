from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student_academics.models import AcademicTerm, AcademicTermStatus
from app.modules.subscriptions.models import PaymentTransaction, TermPlanEntitlement
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    PaymentStatus,
    SubscriptionStatus,
)
from app.modules.subscriptions.term_entitlement_service import (
    PAID_TERM_PLANS,
    TermPlanEntitlementService,
)
from app.modules.simulation.schemas import (
    SubscriptionReconcileResponse,
    SubscriptionSimulationRequest,
    SubscriptionSimulationResponse,
    SubscriptionSimulationScenario,
    SubscriptionSimulationState,
)
from app.tenant_management.models import SubscriptionPlan


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SubscriptionSimulationService:
    """Staging-only term entitlement simulator; it never contacts Paystack."""

    @staticmethod
    async def _term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID | None = None,
        *,
        lock: bool = False,
    ) -> AcademicTerm:
        query = select(AcademicTerm).where(AcademicTerm.tenant_id == tenant_id)
        if term_id is not None:
            query = query.where(AcademicTerm.id == term_id)
        else:
            query = query.order_by(AcademicTerm.is_current.desc(), AcademicTerm.created_at.desc())
        if lock:
            query = query.with_for_update()
        term = (await db.execute(query.limit(1))).scalar_one_or_none()
        if term is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Academic term not found."
            )
        return term

    @staticmethod
    async def _latest_payment(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID
    ) -> PaymentTransaction | None:
        return (
            await db.execute(
                select(PaymentTransaction)
                .where(
                    PaymentTransaction.tenant_id == tenant_id,
                    PaymentTransaction.academic_term_id == term_id,
                )
                .order_by(PaymentTransaction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def _state(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID | None = None
    ) -> SubscriptionSimulationState:
        term = await SubscriptionSimulationService._term(db, tenant_id, term_id)
        entitlement = await TermPlanEntitlementService.get_active(db, tenant_id, term.id)
        payment = await SubscriptionSimulationService._latest_payment(db, tenant_id, term.id)
        if entitlement is None:
            entitlement = (
                await db.execute(
                    select(TermPlanEntitlement)
                    .where(
                        TermPlanEntitlement.tenant_id == tenant_id,
                        TermPlanEntitlement.academic_term_id == term.id,
                    )
                    .order_by(TermPlanEntitlement.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        return SubscriptionSimulationState(
            tenant_id=tenant_id,
            academic_term_id=term.id,
            term_status=term.status.value,
            entitlement_id=getattr(entitlement, "id", None),
            plan_code=getattr(
                getattr(entitlement, "plan_code", None), "value", SubscriptionPlan.FREE.value
            ),
            status=getattr(getattr(entitlement, "status", None), "value", "not_activated"),
            activated_at=getattr(entitlement, "activated_at", None),
            closed_at=getattr(entitlement, "closed_at", None),
            expired_at=getattr(entitlement, "expired_at", None),
            safety_expires_at=getattr(entitlement, "safety_expires_at", None),
            payment_reference=getattr(payment, "reference", None),
            payment_status=getattr(getattr(payment, "status", None), "value", None),
        )

    @staticmethod
    async def _create_pending_payment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        plan: SubscriptionPlan,
    ) -> PaymentTransaction:
        if plan not in PAID_TERM_PLANS:
            plan = SubscriptionPlan.PLUS
        amount_kobo = TermPlanEntitlementService.amount_kobo(plan)
        payment = PaymentTransaction(
            tenant_id=tenant_id,
            academic_term_id=term_id,
            provider=PaymentProvider.PAYSTACK,
            status=PaymentStatus.PENDING,
            reference=f"simulation-term-{uuid.uuid4().hex}",
            plan_code=plan,
            billing_interval=BillingInterval.TERM,
            amount=Decimal(amount_kobo) / 100,
            amount_kobo=amount_kobo,
            currency="NGN",
        )
        db.add(payment)
        await db.flush()
        return payment

    @staticmethod
    def _success_payload(payment: PaymentTransaction, **overrides: object) -> dict:
        metadata = {
            "tenant_id": str(payment.tenant_id),
            "academic_term_id": str(payment.academic_term_id),
            "plan_code": payment.plan_code.value,
        }
        data = {
            "status": "success",
            "reference": payment.reference,
            "amount": payment.amount_kobo,
            "currency": payment.currency,
            "metadata": metadata,
        }
        data.update(overrides)
        return {"data": data}

    @staticmethod
    async def get_state(db: AsyncSession, *, tenant_id: uuid.UUID) -> SubscriptionSimulationState:
        return await SubscriptionSimulationService._state(db, tenant_id)

    @staticmethod
    async def simulate(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: SubscriptionSimulationRequest,
    ) -> SubscriptionSimulationResponse:
        term = await SubscriptionSimulationService._term(
            db, tenant_id, payload.academic_term_id, lock=True
        )
        scenario = payload.scenario
        detail = "Simulation applied."

        if scenario == SubscriptionSimulationScenario.ACTIVATE_FREE:
            await TermPlanEntitlementService.activate_free(db, tenant_id, term.id, None)
            detail = "Free entitlement activated without a provider call."
        elif scenario == SubscriptionSimulationScenario.INITIALIZE_PAID:
            await SubscriptionSimulationService._create_pending_payment(
                db, tenant_id, term.id, payload.plan_code
            )
            await db.commit()
            detail = "Pending paid-term transaction created without contacting Paystack."
        elif scenario in {
            SubscriptionSimulationScenario.PAYMENT_SUCCESS,
            SubscriptionSimulationScenario.DUPLICATE_WEBHOOK,
            SubscriptionSimulationScenario.WRONG_AMOUNT,
            SubscriptionSimulationScenario.WRONG_TERM,
            SubscriptionSimulationScenario.UPGRADE_TO_PROFESSIONAL,
        }:
            target = (
                SubscriptionPlan.PROFESSIONAL
                if scenario == SubscriptionSimulationScenario.UPGRADE_TO_PROFESSIONAL
                else payload.plan_code
            )
            payment = await SubscriptionSimulationService._latest_payment(db, tenant_id, term.id)
            if (
                payment is None
                or payment.status != PaymentStatus.PENDING
                or payment.plan_code != target
            ):
                payment = await SubscriptionSimulationService._create_pending_payment(
                    db, tenant_id, term.id, target
                )
            provider_payload = SubscriptionSimulationService._success_payload(payment)
            if scenario == SubscriptionSimulationScenario.WRONG_AMOUNT:
                provider_payload["data"]["amount"] = payment.amount_kobo + 1
            if scenario == SubscriptionSimulationScenario.WRONG_TERM:
                provider_payload["data"]["metadata"]["academic_term_id"] = str(uuid.uuid4())
            try:
                await TermPlanEntitlementService.activate_verified_transaction(
                    db, payment, provider_payload
                )
                if scenario == SubscriptionSimulationScenario.DUPLICATE_WEBHOOK:
                    await TermPlanEntitlementService.activate_verified_transaction(
                        db, payment, provider_payload
                    )
                detail = (
                    "Paid term entitlement activated; duplicate processing remained idempotent."
                )
            except Exception:
                await db.rollback()
                detail = "Invalid simulated payment was rejected; no entitlement was activated."
        elif scenario == SubscriptionSimulationScenario.PAYMENT_FAILURE:
            payment = await SubscriptionSimulationService._latest_payment(db, tenant_id, term.id)
            if payment is None:
                payment = await SubscriptionSimulationService._create_pending_payment(
                    db, tenant_id, term.id, payload.plan_code
                )
            payment.status = PaymentStatus.FAILED
            payment.failure_reason = "Simulated provider failure"
            await db.commit()
            detail = "Payment failure recorded without activating an entitlement."
        elif scenario == SubscriptionSimulationScenario.CLOSE_TERM:
            await TermPlanEntitlementService.close_for_term(db, tenant_id, term.id)
            now = _now()
            term.status = AcademicTermStatus.CLOSED
            term.is_current = False
            term.closing_started_at = term.closing_started_at or now
            term.closed_at = now
            await db.commit()
            detail = "Term and active entitlement closed together."
        elif scenario == SubscriptionSimulationScenario.TRIAL_EXPIRED:
            trial = await SubscriptionRepository.get_current_subscription(db, tenant_id)
            if trial and trial.plan_code == SubscriptionPlan.FREE_TRIAL:
                trial.trial_ends_at = _now() - timedelta(seconds=1)
                trial.current_period_end = trial.trial_ends_at
                trial.status = SubscriptionStatus.EXPIRED
                trial.is_current = False
                await db.commit()
            detail = "Trial expired; effective-plan fallback is Free."
        elif scenario == SubscriptionSimulationScenario.CLOSED_ACTIVE_RECONCILIATION:
            now = _now()
            term.status = AcademicTermStatus.CLOSED
            term.is_current = False
            term.closing_started_at = term.closing_started_at or now
            term.closed_at = now
            await db.commit()
            await TermPlanEntitlementService.reconcile(db)
            detail = "Reconciliation repaired a CLOSED-term/ACTIVE-entitlement mismatch."
        elif scenario == SubscriptionSimulationScenario.SAFETY_CAP_EXPIRED:
            entitlement = await TermPlanEntitlementService.get_active(
                db, tenant_id, term.id, lock=True
            )
            if entitlement is None:
                raise HTTPException(status_code=409, detail="Activate a term entitlement first.")
            entitlement.safety_expires_at = _now() - timedelta(seconds=1)
            await db.commit()
            await TermPlanEntitlementService.reconcile(db)
            detail = "Safety-cap reconciliation expired the entitlement."

        return SubscriptionSimulationResponse(
            scenario=scenario.value,
            detail=detail,
            state=await SubscriptionSimulationService._state(db, tenant_id, term.id),
        )

    @staticmethod
    async def reconcile(db: AsyncSession, *, tenant_id: uuid.UUID) -> SubscriptionReconcileResponse:
        lifecycle = await TermPlanEntitlementService.reconcile(db)
        return SubscriptionReconcileResponse(
            detail="Term-entitlement safety reconciliation completed.",
            lifecycle=lifecycle,
            state=await SubscriptionSimulationService._state(db, tenant_id),
        )

    @staticmethod
    async def reset(db: AsyncSession, *, tenant_id: uuid.UUID) -> SubscriptionSimulationResponse:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Term lifecycle simulations are auditable and cannot be reset. Use a disposable staging tenant.",
        )
