import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.subjects.models import Subject
from app.modules.subjects.repository import SubjectRepository
from app.modules.subjects.schemas import SubjectCreate, SubjectResponse, SubjectUpdate
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


class SubjectService:
    """Business logic for tenant-configured subjects."""

    @staticmethod
    def _ensure_tenant_admin(actor: TenantAdmin) -> None:
        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant.")

    @staticmethod
    def _ensure_tenant_actor(actor: TenantAdmin | Teacher) -> None:
        if not actor.tenant_id:
            raise ForbiddenException(detail="Actor is not attached to a tenant.")

    @staticmethod
    def normalize_subject_name(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip()).casefold()

    @staticmethod
    def normalize_subject_code(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", "", value.strip()).upper()
        return cleaned or None

    @staticmethod
    def _live_dependency_message(counts: dict[str, int]) -> str | None:
        if counts.get("active_curriculum_subjects", 0) > 0:
            return (
                "This subject is still active in one or more curricula. "
                "Remove or deactivate those curriculum entries first."
            )
        if counts.get("active_teacher_links", 0) > 0:
            return (
                "This subject still has active teacher capability links. "
                "Remove those capabilities first."
            )
        if counts.get("active_teacher_assignments", 0) > 0:
            return "This subject still has active teacher assignments. End those assignments first."
        return None

    @staticmethod
    async def _ensure_no_live_dependencies(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> None:
        counts = await SubjectRepository.count_live_subject_dependencies(
            db=db,
            tenant_id=tenant_id,
            subject_id=subject_id,
        )
        message = SubjectService._live_dependency_message(counts)
        if message:
            raise ConflictException(
                detail=message,
                payload={"dependency_counts": counts},
            )

    @staticmethod
    async def create_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_data: SubjectCreate,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        normalized_name = SubjectService.normalize_subject_name(subject_data.name)
        existing_name = await SubjectRepository.get_subject_by_normalized_name(
            db=db,
            tenant_id=actor.tenant_id,
            normalized_name=normalized_name,
        )
        if existing_name:
            raise BadRequestException(detail="A subject with this name already exists.")
        normalized_code = SubjectService.normalize_subject_code(subject_data.code)
        if normalized_code:
            existing_code = await SubjectRepository.get_subject_by_normalized_code(
                db=db,
                tenant_id=actor.tenant_id,
                normalized_code=normalized_code,
            )
            if existing_code:
                raise BadRequestException(detail="A subject with this code already exists.")
        subject = Subject(
            tenant_id=actor.tenant_id,
            name=subject_data.name,
            normalized_name=normalized_name,
            code=normalized_code,
            normalized_code=normalized_code,
            description=subject_data.description,
            is_active=True,
            archived_at=None,
            archived_by_admin_id=None,
        )
        try:
            created_subject = await SubjectRepository.create_subject(db=db, subject=subject)
            await db.commit()
            subject_with_teachers = await SubjectRepository.get_subject_by_id(
                db=db,
                tenant_id=actor.tenant_id,
                subject_id=created_subject.id,
            )
            if not subject_with_teachers:
                raise NotFoundException(detail="Subject not found after creation.")
            return subject_with_teachers
        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException(
                detail="Subject creation failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def get_subject(
        db: AsyncSession,
        actor: TenantAdmin | Teacher,
        subject_id: UUID,
    ) -> Subject:
        if not isinstance(actor, (TenantAdmin, Teacher)):
            raise ForbiddenException(detail="You are not allowed to view subjects.")
        SubjectService._ensure_tenant_actor(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")
        if isinstance(actor, Teacher) and subject.archived_at is not None:
            raise NotFoundException(detail="Subject not found.")
        return subject

    @staticmethod
    async def list_subjects(
        db: AsyncSession,
        actor: TenantAdmin | Teacher,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
        search: str | None = None,
        include_archived: bool = False,
        lifecycle_status: str | None = None,
    ) -> tuple[list[Subject], int]:
        if not isinstance(actor, (TenantAdmin, Teacher)):
            raise ForbiddenException(detail="You are not allowed to view subjects.")
        SubjectService._ensure_tenant_actor(actor)
        limit = min(limit, 500)
        if isinstance(actor, Teacher):
            return await SubjectRepository.list_subjects_for_teacher(
                db=db,
                tenant_id=actor.tenant_id,
                teacher_id=actor.id,
                skip=skip,
                limit=limit,
                is_active=is_active,
                search=search,
            )
        return await SubjectRepository.list_all_subjects(
            db=db,
            tenant_id=actor.tenant_id,
            skip=skip,
            limit=limit,
            is_active=is_active,
            search=search,
            include_archived=include_archived,
            lifecycle_status=lifecycle_status,
        )

    @staticmethod
    async def update_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
        subject_data: SubjectUpdate,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")
        if subject.archived_at is not None:
            raise ConflictException("Archived subjects cannot be updated. Restore them first.")
        update_data = subject_data.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException(detail="No update data provided.")
        if "name" in update_data:
            normalized_name = SubjectService.normalize_subject_name(update_data["name"])
            if normalized_name != subject.normalized_name:
                existing_name = await SubjectRepository.get_subject_by_normalized_name(
                    db=db,
                    tenant_id=actor.tenant_id,
                    normalized_name=normalized_name,
                )
                if existing_name:
                    raise BadRequestException(detail="A subject with this name already exists.")
            update_data["normalized_name"] = normalized_name
        if "code" in update_data:
            normalized_code = SubjectService.normalize_subject_code(update_data["code"])
            if normalized_code and normalized_code != subject.normalized_code:
                existing_code = await SubjectRepository.get_subject_by_normalized_code(
                    db=db,
                    tenant_id=actor.tenant_id,
                    normalized_code=normalized_code,
                )
                if existing_code:
                    raise BadRequestException(detail="A subject with this code already exists.")
            update_data["normalized_code"] = normalized_code
            update_data["code"] = normalized_code
        try:
            for field, value in update_data.items():
                setattr(subject, field, value)
            updated_subject = await SubjectRepository.update_subject(db=db, subject=subject)
            await db.commit()
            subject_with_teachers = await SubjectRepository.get_subject_by_id(
                db=db,
                tenant_id=actor.tenant_id,
                subject_id=updated_subject.id,
            )
            if not subject_with_teachers:
                raise NotFoundException(detail="Subject not found after update.")
            return subject_with_teachers
        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException(
                detail="Subject update failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def activate_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")
        if subject.archived_at is not None:
            raise ConflictException("Archived subjects must be restored before activation.")
        if subject.is_active:
            return subject
        subject.is_active = True
        await SubjectRepository.update_subject(db=db, subject=subject)
        await db.commit()
        subject_with_teachers = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject.id,
        )
        if not subject_with_teachers:
            raise NotFoundException(detail="Subject not found after activation.")
        return subject_with_teachers

    @staticmethod
    async def archive_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if subject is None:
            raise NotFoundException("Subject not found")
        if subject.archived_at is not None:
            return subject
        if subject.is_active:
            raise ConflictException(
                "Active subjects cannot be archived. Deactivate the subject first."
            )
        await SubjectService._ensure_no_live_dependencies(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject.id,
        )
        subject.archived_at = datetime.now(timezone.utc)
        subject.archived_by_admin_id = actor.id
        await SubjectRepository.update_subject(db=db, subject=subject)
        await db.commit()
        return subject

    @staticmethod
    async def deactivate_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")
        if subject.archived_at is not None:
            raise ConflictException("Archived records cannot be deactivated. Restore them first.")
        if not subject.is_active:
            return subject
        await SubjectService._ensure_no_live_dependencies(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject.id,
        )
        subject.is_active = False
        await SubjectRepository.update_subject(db=db, subject=subject)
        await db.commit()
        subject_with_teachers = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject.id,
        )
        if not subject_with_teachers:
            raise NotFoundException(detail="Subject not found after deactivation.")
        return subject_with_teachers

    @staticmethod
    async def purge_setup_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> SubjectResponse:
        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")
        dependency_counts = await SubjectRepository.count_subject_dependencies(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject.id,
        )
        if any(count > 0 for count in dependency_counts.values()):
            raise ConflictException(
                detail="This subject is already referenced and cannot be removed from setup.",
                payload={"dependency_counts": dependency_counts},
            )
        response = SubjectResponse.model_validate(subject)
        await SubjectRepository.delete_subject(db=db, subject=subject)
        await db.commit()
        return response

    @staticmethod
    async def restore_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if subject is None:
            raise NotFoundException("Subject not found")
        if subject.archived_at is None:
            return subject
        subject.archived_at = None
        subject.archived_by_admin_id = None
        subject.is_active = False
        await SubjectRepository.update_subject(db=db, subject=subject)
        await db.commit()
        return subject

    @staticmethod
    async def delete_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> None:
        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")
        if subject.is_active:
            raise ConflictException(
                "Active subjects cannot be deleted. Deactivate the subject first."
            )
        if subject.archived_at is not None:
            raise ConflictException("Archived subjects cannot be deleted. Restore them first.")
        dependency_counts = await SubjectRepository.count_subject_dependencies(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject.id,
        )
        if any(count > 0 for count in dependency_counts.values()):
            raise ConflictException(
                detail="Subject has academic dependencies and cannot be deleted.",
                payload={"dependency_counts": dependency_counts},
            )
        await SubjectRepository.delete_subject(db=db, subject=subject)
        await db.commit()
