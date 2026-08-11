"""Teacher subject capability read and replacement contracts."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics.models import (
    LevelSubject,
    TeacherAssignment,
)
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.repository import (
    TeacherMembershipRepository,
    TeacherMembershipSubjectRepository,
)
from app.modules.teachers.schemas import (
    TeacherMembershipResponse,
    TeacherMembershipSubjectUpdateRequest,
)
from app.modules.teachers.service import TeacherMembershipService
from app.modules.tenant_admins.models import TenantAdmin


class TeacherSubjectCapabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject_id: UUID
    subject_name: str
    subject_code: str | None = None
    is_active: bool


class TeacherSubjectCapabilityListResponse(BaseModel):
    items: list[TeacherSubjectCapabilityResponse]
    total: int


class TeacherSubjectCapabilityService:
    @staticmethod
    async def list_capabilities(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        membership_id: UUID,
    ) -> TeacherSubjectCapabilityListResponse:
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=tenant_id,
        )
        if membership is None:
            raise NotFoundException("Teacher membership not found.")

        links = await TeacherMembershipSubjectRepository.list_for_membership(
            db,
            tenant_id,
            membership_id,
        )
        items = [
            TeacherSubjectCapabilityResponse(
                subject_id=link.subject_id,
                subject_name=link.subject.name,
                subject_code=getattr(link.subject, "code", None),
                is_active=link.is_active,
            )
            for link in links
        ]
        return TeacherSubjectCapabilityListResponse(items=items, total=len(items))

    @staticmethod
    async def replace_capabilities(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        membership_id: UUID,
        payload: TeacherMembershipSubjectUpdateRequest,
    ) -> TeacherMembershipResponse:
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=actor.tenant_id,
            lock=True,
            load_account=True,
            load_subjects=True,
        )
        if membership is None:
            raise NotFoundException("Teacher membership not found.")

        requested = set(payload.subject_ids)
        for subject_id in requested:
            subject = await SubjectRepository.get_subject_by_id(
                db,
                actor.tenant_id,
                subject_id,
            )
            if subject is None or not subject.is_active:
                raise NotFoundException(f"Subject {subject_id} was not found or is inactive.")

        existing_links = await TeacherMembershipSubjectRepository.list_for_membership(
            db,
            actor.tenant_id,
            membership_id,
        )
        existing_active = {link.subject_id for link in existing_links if link.is_active}
        removed = existing_active - requested

        if removed:
            current_assignment_subjects = set(
                (
                    await db.execute(
                        select(LevelSubject.subject_id)
                        .join(
                            TeacherAssignment,
                            TeacherAssignment.level_subject_id == LevelSubject.id,
                        )
                        .where(
                            TeacherAssignment.tenant_id == actor.tenant_id,
                            TeacherAssignment.teacher_membership_id == membership_id,
                            TeacherAssignment.is_active.is_(True),
                            LevelSubject.subject_id.in_(removed),
                        )
                    )
                )
                .scalars()
                .all()
            )
            blocked = current_assignment_subjects
            if blocked:
                raise ConflictException(
                    "An approved subject cannot be removed while an active "
                    "teaching assignment depends on it. Reassign or end the "
                    "assignment first."
                )

        return await TeacherMembershipService.replace_subject_capabilities(
            db,
            actor=actor,
            membership_id=membership_id,
            payload=payload,
        )
