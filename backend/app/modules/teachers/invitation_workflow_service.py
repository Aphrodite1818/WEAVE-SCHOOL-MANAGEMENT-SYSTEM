"""Teacher invitation workflow with tenant onboarding and staff-ID policies."""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_auth_secret
from app.modules.teachers.models import TeacherAccount
from app.modules.teachers.repository import TeacherInvitationRepository
from app.modules.teachers.schemas import (
    TeacherInvitationAcceptanceRequest,
    TeacherInvitationCreateRequest,
    TeacherInvitationResponse,
    TeacherMembershipWithAccountResponse,
)
from app.modules.teachers.service import (
    TeacherInvitationCreateCommand,
    TeacherInvitationService,
)
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.identifier_service import (
    TenantIdentifierKind,
    TenantIdentifierService,
)


class TeacherInvitationWorkflowService:
    """Apply onboarding and identifier rules around canonical invitation logic."""

    @staticmethod
    async def create_invitation(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        payload: TeacherInvitationCreateRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> TeacherInvitationResponse:
        """Create an invitation with an automatically reserved staff ID."""

        tenant = await TenantIdentifierService.require_completed_onboarding(
            db,
            tenant_id=actor.tenant_id,
            lock=True,
        )
        staff_id = await TenantIdentifierService.generate_identifier(
            db,
            tenant=tenant,
            kind=TenantIdentifierKind.TEACHER,
        )
        command = TeacherInvitationCreateCommand(
            email=str(payload.email).casefold(),
            staff_id=staff_id,
            job_title=payload.job_title,
            department=payload.department,
            employment_type=payload.employment_type,
        )
        return await TeacherInvitationService.create_invitation(
            db,
            actor=actor,
            payload=command,
            background_tasks=background_tasks,
        )

    @staticmethod
    async def accept_invitation(
        db: AsyncSession,
        *,
        account: TeacherAccount,
        payload: TeacherInvitationAcceptanceRequest,
    ) -> TeacherMembershipWithAccountResponse:
        """Accept an invitation and replace null or legacy-format staff IDs."""

        token_digest = hash_auth_secret(payload.invitation_token)
        preview = await TeacherInvitationRepository.get_by_token_digest(
            db,
            token_digest,
        )
        if preview is not None:
            tenant = await TenantIdentifierService.require_completed_onboarding(
                db,
                tenant_id=preview.tenant_id,
                lock=True,
            )
            invitation = await TeacherInvitationRepository.get_by_token_digest(
                db,
                token_digest,
                lock=True,
            )
            if invitation is not None and not (
                TenantIdentifierService.is_canonical_identifier(
                    tenant=tenant,
                    value=invitation.staff_id,
                )
            ):
                invitation.staff_id = await TenantIdentifierService.generate_identifier(
                    db,
                    tenant=tenant,
                    kind=TenantIdentifierKind.TEACHER,
                )
                await TeacherInvitationRepository.save(db, invitation)

        return await TeacherInvitationService.accept_invitation(
            db,
            account=account,
            payload=payload,
        )
