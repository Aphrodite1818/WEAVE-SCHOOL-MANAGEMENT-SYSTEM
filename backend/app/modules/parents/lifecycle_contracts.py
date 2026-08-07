"""Parent membership and student-link lifecycle contracts.

This module keeps cross-aggregate lifecycle behavior out of the account/profile
service. It owns operations that must keep parent memberships, student links,
sessions, and subscription usage consistent in one transaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.auth.models import AuthSession, AuthSessionActorType
from app.modules.parents.models import ParentMembership, ParentMembershipStatus
from app.modules.parents.repository import ParentMembershipRepository
from app.modules.parents.schemas import (
    ParentMembershipReactivateRequest,
    ParentMembershipResponse,
)
from app.modules.parents.service import ParentMembershipService
from app.modules.students.models import AcademicStatus, StudentParentLinkStatus
from app.modules.students.repository import (
    StudentParentLinkRepository,
    StudentParentLinkRequestRepository,
    StudentRepository,
)
from app.modules.students.schemas import (
    StudentDetailResponse,
    StudentParentLinkEndRequest,
    StudentParentLinkReactivateRequest,
    StudentParentLinkRequestDetailResponse,
    StudentParentLinkResponse,
)
from app.modules.students.service import (
    StudentLifecycleService,
    StudentParentLinkRequestService,
    StudentService,
)
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.tenant_admins.models import TenantAdmin


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ParentLinkedStudentItem(OutputBase):
    student: StudentDetailResponse
    link: StudentParentLinkResponse


class ParentLinkedStudentListResponse(OutputBase):
    items: list[ParentLinkedStudentItem]
    total: int = Field(ge=0)


class AdminParentLinkItem(OutputBase):
    student: StudentDetailResponse
    link: StudentParentLinkResponse


class AdminParentLinkListResponse(OutputBase):
    items: list[AdminParentLinkItem]
    total: int = Field(ge=0)


class ParentMembershipLifecycleService:
    """Keep parent memberships and child links mutually consistent."""

    @staticmethod
    async def _revoke_membership_sessions(
        db: AsyncSession,
        *,
        membership: ParentMembership,
        reason: str,
    ) -> None:
        await db.execute(
            update(AuthSession)
            .where(
                AuthSession.actor_type == AuthSessionActorType.PARENT,
                AuthSession.actor_id == membership.id,
                AuthSession.tenant_id == membership.tenant_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(
                revoked_at=_utc_now(),
                revoked_reason=reason[:100],
            )
        )

    @staticmethod
    def _status_for_student(student_status: AcademicStatus) -> StudentParentLinkStatus:
        if student_status == AcademicStatus.GRADUATED:
            return StudentParentLinkStatus.ALUMNI_READ_ONLY
        if student_status == AcademicStatus.WITHDRAWN:
            return StudentParentLinkStatus.READ_ONLY
        if student_status == AcademicStatus.EXPELLED:
            return StudentParentLinkStatus.ENDED
        return StudentParentLinkStatus.ACTIVE

    @staticmethod
    async def list_children_with_links(
        db: AsyncSession,
        *,
        membership: ParentMembership,
    ) -> ParentLinkedStudentListResponse:
        links = await StudentParentLinkRepository.list_for_membership(
            db,
            membership.tenant_id,
            membership.id,
            statuses=[
                StudentParentLinkStatus.ACTIVE,
                StudentParentLinkStatus.READ_ONLY,
                StudentParentLinkStatus.ALUMNI_READ_ONLY,
            ],
        )
        items: list[ParentLinkedStudentItem] = []
        for link in links:
            if link.student is None:
                continue
            items.append(
                ParentLinkedStudentItem(
                    student=await StudentService._build_detail_response(
                        db, link.student
                    ),
                    link=StudentParentLinkResponse.model_validate(link),
                )
            )
        return ParentLinkedStudentListResponse(items=items, total=len(items))

    @staticmethod
    async def list_membership_links(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        membership_id: UUID,
    ) -> AdminParentLinkListResponse:
        membership = await ParentMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=tenant_id,
            load_account=True,
        )
        if membership is None:
            raise NotFoundException("Parent membership not found.")
        links = await StudentParentLinkRepository.list_for_membership(
            db,
            tenant_id,
            membership_id,
        )
        items: list[AdminParentLinkItem] = []
        for link in links:
            if link.student is None:
                continue
            items.append(
                AdminParentLinkItem(
                    student=await StudentService._build_detail_response(
                        db, link.student
                    ),
                    link=StudentParentLinkResponse.model_validate(link),
                )
            )
        return AdminParentLinkListResponse(items=items, total=len(items))

    @staticmethod
    async def reactivate_membership(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        membership_id: UUID,
        payload: ParentMembershipReactivateRequest,
    ) -> ParentMembershipResponse:
        membership = await ParentMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=actor.tenant_id,
            lock=True,
            load_account=True,
        )
        if membership is None:
            raise NotFoundException("Parent membership not found.")
        if membership.status != ParentMembershipStatus.INACTIVE:
            raise ConflictException("Parent membership is already usable.")

        ended_at = membership.ended_at
        await ParentMembershipService._lock_tenant_and_enforce_limit(
            db,
            tenant_id=actor.tenant_id,
        )

        links = await StudentParentLinkRepository.list_for_membership(
            db,
            actor.tenant_id,
            membership.id,
            statuses=[StudentParentLinkStatus.ENDED],
            lock=True,
        )
        restored = 0
        for link in links:
            if ended_at is None or link.ended_at != ended_at or link.student is None:
                continue
            target_status = ParentMembershipLifecycleService._status_for_student(
                link.student.status
            )
            if target_status == StudentParentLinkStatus.ENDED:
                continue
            link.status = target_status
            link.ended_at = None
            link.end_reason = None
            await StudentParentLinkRepository.save(db, link)
            restored += 1

        if restored == 0:
            raise ConflictException(
                "No child links are eligible for automatic restoration. "
                "Reactivate an individual parent link instead."
            )

        await StudentLifecycleService._recalculate_parent_membership(db, membership)
        await db.commit()
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(
            actor.tenant_id
        )
        await db.refresh(membership)
        return ParentMembershipResponse.model_validate(membership)

    @staticmethod
    async def end_link(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        link_id: UUID,
        payload: StudentParentLinkEndRequest,
    ) -> StudentParentLinkResponse:
        link = await StudentParentLinkRepository.get_by_id(
            db,
            actor.tenant_id,
            link_id,
            lock=True,
        )
        if link is None:
            raise NotFoundException("Parent link not found.")
        if link.status == StudentParentLinkStatus.ENDED:
            raise ConflictException("Parent link is already ended.")

        now = _utc_now()
        link.status = StudentParentLinkStatus.ENDED
        link.ended_at = now
        link.end_reason = payload.reason
        await StudentParentLinkRepository.save(db, link)

        membership = await ParentMembershipRepository.get_by_id(
            db,
            link.parent_membership_id,
            tenant_id=actor.tenant_id,
            lock=True,
            load_account=True,
        )
        if membership is None:
            raise ConflictException("Parent membership no longer exists.")
        await StudentLifecycleService._recalculate_parent_membership(db, membership)
        if membership.status == ParentMembershipStatus.INACTIVE:
            await ParentMembershipLifecycleService._revoke_membership_sessions(
                db,
                membership=membership,
                reason="last_parent_link_ended",
            )

        await db.commit()
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(
            actor.tenant_id
        )
        await db.refresh(link)
        return StudentParentLinkResponse.model_validate(link)

    @staticmethod
    async def reactivate_link(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        link_id: UUID,
        payload: StudentParentLinkReactivateRequest,
    ) -> StudentParentLinkResponse:
        link = await StudentParentLinkRepository.get_by_id(
            db,
            actor.tenant_id,
            link_id,
            lock=True,
        )
        if link is None:
            raise NotFoundException("Parent link not found.")
        if link.status != StudentParentLinkStatus.ENDED:
            raise ConflictException("Only ended parent links can be reactivated.")

        student = await StudentRepository.get_by_id(
            db,
            actor.tenant_id,
            link.student_id,
            lock=True,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        if student.status == AcademicStatus.EXPELLED:
            raise BadRequestException(
                "An expelled student's parent link cannot be reactivated."
            )

        membership = await ParentMembershipRepository.get_by_id(
            db,
            link.parent_membership_id,
            tenant_id=actor.tenant_id,
            lock=True,
            load_account=True,
        )
        if membership is None:
            raise ConflictException("Parent membership no longer exists.")
        if membership.status == ParentMembershipStatus.INACTIVE:
            await ParentMembershipService._lock_tenant_and_enforce_limit(
                db,
                tenant_id=actor.tenant_id,
            )

        link.status = ParentMembershipLifecycleService._status_for_student(
            student.status
        )
        link.is_primary_contact = payload.is_primary_contact
        link.receives_academic_updates = payload.receives_academic_updates
        link.receives_fee_updates = payload.receives_fee_updates
        link.ended_at = None
        link.end_reason = None
        await StudentParentLinkRepository.save(db, link)
        await StudentLifecycleService._recalculate_parent_membership(db, membership)

        await db.commit()
        await SubscriptionFeatureService.invalidate_tenant_subscription_state(
            actor.tenant_id
        )
        await db.refresh(link)
        return StudentParentLinkResponse.model_validate(link)

    @staticmethod
    async def list_pending_requests(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        skip: int,
        limit: int,
    ) -> tuple[list[StudentParentLinkRequestDetailResponse], int]:
        rows, total = await StudentParentLinkRequestRepository.list_pending_for_tenant(
            db,
            tenant_id,
            offset=skip,
            limit=limit,
        )
        return [
            await StudentParentLinkRequestService._detail(db, row) for row in rows
        ], total
