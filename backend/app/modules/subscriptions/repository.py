from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.classes.models import ClassRoom
from app.modules.parents.models import ParentMembership, ParentMembershipStatus
from app.modules.students.models import Student
from app.modules.subjects.models import Subject
from app.modules.subscriptions.models import (
    PaymentTransaction,
    PaymentWebhookEvent,
    TenantSubscription,
)
from app.modules.subscriptions.subscription_enums import (
    PaymentProvider,
    PaymentStatus,
    ResourceLimitCode,
    SubscriptionStatus,
)
from app.modules.teachers.models import TeacherMembership, TeacherMembershipStatus
from app.tenant_management.models import (
    SubscriptionPlan,
    Tenant,
    TenantStatus,
    TenantVerificationStatus,
)


class SubscriptionRepository:
    @staticmethod
    async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def save_tenant(db: AsyncSession, tenant: Tenant) -> Tenant:
        db.add(tenant)
        await db.flush()
        return tenant

    @staticmethod
    async def update_tenant_plan_snapshot(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        plan_code: SubscriptionPlan,
        subscription_status: SubscriptionStatus,
        current_period_end: datetime | None,
        trial_ends_at: datetime | None,
    ) -> Tenant | None:
        tenant = await SubscriptionRepository.get_tenant(db, tenant_id)
        if tenant is None:
            return None
        tenant.plan = plan_code
        tenant.trial_ends_at = trial_ends_at
        tenant.subscription_ends_at = current_period_end
        if tenant.verification_status == TenantVerificationStatus.ACTIVE:
            # Tenant account activity and subscription activity are separate.
            # Expired billing must keep Billing and historical records accessible;
            # subscription guards decide which writes remain available.
            tenant.status = (
                TenantStatus.TRIAL
                if subscription_status == SubscriptionStatus.TRIALING
                else TenantStatus.ACTIVE
            )
        return await SubscriptionRepository.save_tenant(db, tenant)

    @staticmethod
    async def get_tenant_plan(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> SubscriptionPlan | None:
        tenant = await SubscriptionRepository.get_tenant(db, tenant_id)
        return None if tenant is None else getattr(tenant, "plan", None)

    @staticmethod
    async def get_current_subscription(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> TenantSubscription | None:
        query = (
            select(TenantSubscription)
            .where(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.is_current.is_(True),
            )
            .order_by(TenantSubscription.updated_at.desc())
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_subscription_by_id(
        db: AsyncSession,
        subscription_id: uuid.UUID,
    ) -> TenantSubscription | None:
        result = await db.execute(
            select(TenantSubscription).where(TenantSubscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_subscription(
        db: AsyncSession,
        subscription: TenantSubscription,
    ) -> TenantSubscription:
        db.add(subscription)
        await db.flush()
        return subscription

    @staticmethod
    async def save_subscription(
        db: AsyncSession,
        subscription: TenantSubscription,
    ) -> TenantSubscription:
        db.add(subscription)
        await db.flush()
        return subscription

    @staticmethod
    async def find_subscriptions_by_tenant_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[TenantSubscription]:
        result = await db.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_pending_payment_transaction(
        db: AsyncSession,
        transaction: PaymentTransaction,
    ) -> PaymentTransaction:
        db.add(transaction)
        await db.flush()
        return transaction

    @staticmethod
    async def save_payment_transaction(
        db: AsyncSession,
        transaction: PaymentTransaction,
    ) -> PaymentTransaction:
        db.add(transaction)
        await db.flush()
        return transaction

    @staticmethod
    async def get_transaction_by_reference(
        db: AsyncSession,
        reference: str,
    ) -> PaymentTransaction | None:
        result = await db.execute(
            select(PaymentTransaction).where(PaymentTransaction.reference == reference)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_payment_transactions(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        status: PaymentStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PaymentTransaction], int]:
        filters = [PaymentTransaction.tenant_id == tenant_id]
        if status is not None:
            filters.append(PaymentTransaction.status == status)
        if date_from is not None:
            filters.append(PaymentTransaction.created_at >= date_from)
        if date_to is not None:
            filters.append(PaymentTransaction.created_at <= date_to)

        total = int(
            (
                await db.execute(
                    select(func.count()).select_from(PaymentTransaction).where(*filters)
                )
            ).scalar_one()
        )
        rows = (
            (
                await db.execute(
                    select(PaymentTransaction)
                    .where(*filters)
                    .order_by(PaymentTransaction.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    @staticmethod
    async def mark_transaction_success(
        db: AsyncSession,
        *,
        transaction: PaymentTransaction,
        provider_transaction_id: str | None,
        paid_at: datetime | None,
        raw_payload: dict | None,
    ) -> PaymentTransaction:
        transaction.status = PaymentStatus.SUCCESS
        transaction.provider_transaction_id = provider_transaction_id
        transaction.paid_at = paid_at
        transaction.failure_reason = None
        transaction.raw_payload = raw_payload
        return await SubscriptionRepository.save_payment_transaction(db, transaction)

    @staticmethod
    async def mark_transaction_failed(
        db: AsyncSession,
        *,
        transaction: PaymentTransaction,
        status: PaymentStatus,
        failure_reason: str | None,
        raw_payload: dict | None,
        provider_transaction_id: str | None = None,
    ) -> PaymentTransaction:
        transaction.status = status
        transaction.failure_reason = failure_reason
        transaction.raw_payload = raw_payload
        transaction.provider_transaction_id = provider_transaction_id
        return await SubscriptionRepository.save_payment_transaction(db, transaction)

    async def create_webhook_event(
        db: AsyncSession,
        webhook_event: PaymentWebhookEvent,
    ) -> PaymentWebhookEvent:
        db.add(webhook_event)
        await db.flush()
        return webhook_event

    @staticmethod
    async def get_webhook_event_by_provider(
        db: AsyncSession,
        *,
        provider: PaymentProvider,
        event_type: str,
        event_key: str,
    ) -> PaymentWebhookEvent | None:
        result = await db.execute(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider == provider,
                PaymentWebhookEvent.event_type == event_type,
                PaymentWebhookEvent.event_key == event_key,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_webhook_processed(
        db: AsyncSession,
        *,
        webhook_event: PaymentWebhookEvent,
        processed_at: datetime,
    ) -> PaymentWebhookEvent:
        webhook_event.processed_at = processed_at
        webhook_event.error_message = None
        webhook_event.payload = webhook_event.payload or {}
        db.add(webhook_event)
        await db.flush()
        return webhook_event

    @staticmethod
    async def mark_webhook_failed(
        db: AsyncSession,
        *,
        webhook_event: PaymentWebhookEvent,
        error_message: str,
    ) -> PaymentWebhookEvent:
        webhook_event.error_message = error_message
        db.add(webhook_event)
        await db.flush()
        return webhook_event

    @staticmethod
    async def get_expirable_subscriptions(
        db: AsyncSession,
        *,
        as_of: datetime,
        limit: int = 100,
    ) -> list[TenantSubscription]:
        result = await db.execute(
            select(TenantSubscription)
            .where(
                TenantSubscription.is_current.is_(True),
                TenantSubscription.plan_code == SubscriptionPlan.FREE_TRIAL,
                TenantSubscription.status == SubscriptionStatus.TRIALING,
                TenantSubscription.trial_ends_at.is_not(None),
                TenantSubscription.trial_ends_at <= as_of,
            )
            .order_by(TenantSubscription.updated_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_students(db: AsyncSession, tenant_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count(Student.id)).where(
                Student.tenant_id == tenant_id,
                Student.is_archived.is_(False),
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def count_teachers(db: AsyncSession, tenant_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count(TeacherMembership.id)).where(
                TeacherMembership.tenant_id == tenant_id,
                TeacherMembership.status == TeacherMembershipStatus.ACTIVE,
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def count_parents(db: AsyncSession, tenant_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count(ParentMembership.id)).where(
                ParentMembership.tenant_id == tenant_id,
                ParentMembership.status == ParentMembershipStatus.ACTIVE,
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def count_classes(db: AsyncSession, tenant_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count(ClassRoom.id)).where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.is_active == True,
                ClassRoom.archived_at.is_(None),
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def count_subjects(db: AsyncSession, tenant_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count(Subject.id)).where(
                Subject.tenant_id == tenant_id,
                Subject.is_active == True,
                Subject.archived_at.is_(None),
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def get_resource_usage(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        resource: ResourceLimitCode,
    ) -> int:
        counter_map = {
            ResourceLimitCode.STUDENTS: SubscriptionRepository.count_students,
            ResourceLimitCode.TEACHERS: SubscriptionRepository.count_teachers,
            ResourceLimitCode.PARENTS: SubscriptionRepository.count_parents,
            ResourceLimitCode.CLASSES: SubscriptionRepository.count_classes,
            ResourceLimitCode.SUBJECTS: SubscriptionRepository.count_subjects,
        }
        return await counter_map[resource](db, tenant_id)

    @staticmethod
    async def get_all_resource_usage(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> dict[ResourceLimitCode, int]:
        return {
            ResourceLimitCode.STUDENTS: await SubscriptionRepository.count_students(db, tenant_id),
            ResourceLimitCode.TEACHERS: await SubscriptionRepository.count_teachers(db, tenant_id),
            ResourceLimitCode.PARENTS: await SubscriptionRepository.count_parents(db, tenant_id),
            ResourceLimitCode.CLASSES: await SubscriptionRepository.count_classes(db, tenant_id),
            ResourceLimitCode.SUBJECTS: await SubscriptionRepository.count_subjects(db, tenant_id),
        }
