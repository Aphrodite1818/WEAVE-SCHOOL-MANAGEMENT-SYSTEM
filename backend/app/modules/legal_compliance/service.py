"""Service layer for legal compliance acceptance."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.legal_compliance.models import LegalComplianceAcceptance
from app.modules.parents.models import Parent, ParentAccount
from app.modules.students.models import Student
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher, TeacherAccount
from app.modules.tenant_admins.models import TenantAdmin

CURRENT_LEGAL_POLICY_VERSION = "weave-legal-compliance-v1"


def _actor_compliance_identity(
    actor: (
        SuperAdmin
        | TenantAdmin
        | Teacher
        | Parent
        | Student
        | TeacherAccount
        | ParentAccount
    ),
) -> tuple[str, uuid.UUID, uuid.UUID | None]:
    if isinstance(actor, SuperAdmin):
        return "superadmin", actor.id, None
    if isinstance(actor, TenantAdmin):
        return "tenant_admin", actor.id, actor.tenant_id
    if isinstance(actor, TeacherAccount):
        return "teacher_account", actor.id, None
    if isinstance(actor, Teacher):
        return "teacher_account", actor.teacher_account_id, actor.tenant_id
    if isinstance(actor, ParentAccount):
        return "parent_account", actor.id, None
    if isinstance(actor, Parent):
        return "parent_account", actor.parent_account_id, actor.tenant_id
    if isinstance(actor, Student):
        return "student", actor.id, actor.tenant_id
    raise TypeError("Unsupported legal compliance actor.")


class LegalComplianceService:
    """Read and write legal compliance acceptance for authenticated actors."""

    @staticmethod
    async def get_status_for_identity(
        db: AsyncSession,
        *,
        actor_type: str,
        actor_id: uuid.UUID,
    ) -> dict[str, object]:
        result = await db.execute(
            select(LegalComplianceAcceptance)
            .where(
                LegalComplianceAcceptance.actor_type == actor_type,
                LegalComplianceAcceptance.actor_id == actor_id,
                LegalComplianceAcceptance.policy_version
                == CURRENT_LEGAL_POLICY_VERSION,
            )
            .order_by(LegalComplianceAcceptance.accepted_at.desc())
        )
        acceptance = result.scalars().first()
        return {
            "policy_version": CURRENT_LEGAL_POLICY_VERSION,
            "accepted": acceptance is not None,
            "accepted_at": acceptance.accepted_at if acceptance else None,
        }

    @staticmethod
    async def get_status(
        db: AsyncSession,
        actor: (
            SuperAdmin
            | TenantAdmin
            | Teacher
            | Parent
            | Student
            | TeacherAccount
            | ParentAccount
        ),
    ) -> dict[str, object]:
        actor_type, actor_id, _ = _actor_compliance_identity(actor)
        return await LegalComplianceService.get_status_for_identity(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
        )

    @staticmethod
    async def accept(
        db: AsyncSession,
        actor: (
            SuperAdmin
            | TenantAdmin
            | Teacher
            | Parent
            | Student
            | TeacherAccount
            | ParentAccount
        ),
    ) -> dict[str, object]:
        status = await LegalComplianceService.get_status(db, actor)
        if status["accepted"]:
            return status

        actor_type, actor_id, tenant_id = _actor_compliance_identity(actor)
        acceptance = LegalComplianceAcceptance(
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor_id,
            policy_version=CURRENT_LEGAL_POLICY_VERSION,
            accepted_at=datetime.now(timezone.utc),
        )
        db.add(acceptance)
        await db.commit()
        await db.refresh(acceptance)
        return {
            "policy_version": CURRENT_LEGAL_POLICY_VERSION,
            "accepted": True,
            "accepted_at": acceptance.accepted_at,
        }
