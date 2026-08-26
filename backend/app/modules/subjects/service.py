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
from app.core.utils.normalization import (
    normalize_display_text,
    normalize_subject_code,
    normalize_subject_name,
)
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.subjects.models import Subject
from app.modules.subjects.repository import SubjectRepository
from app.modules.subjects.schemas import SubjectCreate, SubjectResponse, SubjectUpdate
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


class SubjectService:
    """Business logic for tenant-configured subjects."""

    LIVE_DEPENDENCY_KEYS = (
        "curriculum_subjects_live",
        "teacher_links_live",
        "teacher_assignments_live",
        "results_live",
        "report_card_lines_live",
    )

    @staticmethod
    def _ensure_tenant_admin(actor: TenantAdmin) -> None:
        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant.")

    @staticmethod
    def _ensure_tenant_actor(actor: TenantAdmin | Teacher) -> None:
        if not actor.tenant_id:
            raise ForbiddenException(detail="Actor is not attached to a tenant.")

    @staticmethod
    def _normalize_name(value: str) -> tuple[str, str]:
        name = normalize_display_text(value)
        if not name:
            raise BadRequestException(detail="Subject name is required.")
        normalized_name = normalize_subject_name(name)
        if not normalized_name:
            raise BadRequestException(detail="Subject name is required.")
        return name, normalized_name

    @staticmethod
    def _has_any_usage(counts: dict[str, int]) -> bool:
        return any(value > 0 for key, value in counts.items() if key.endswith("_total"))

    @staticmethod
    def _live_dependency_counts(counts: dict[str, int]) -> dict[str, int]:
        return {
            key: counts.get(key, 0)
            for key in SubjectService.LIVE_DEPENDENCY_KEYS
            if counts.get(key, 0) > 0
        }

    @staticmethod
    async def _ensure_no_live_dependencies(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> None:
        counts = await SubjectRepository.count_dependencies(
            db=db,
            tenant_id=tenant_id,
            subject_id=subject_id,
        )
        live_counts = SubjectService._live_dependency_counts(counts)
        if live_counts:
            raise ConflictException(
                detail="This subject still has live academic dependencies and cannot change lifecycle state.",
                payload={"dependency_counts": live_counts},
            )

    @staticmethod
    async def create_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_data: SubjectCreate,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

        name, normalized_name = SubjectService._normalize_name(subject_data.name)
        existing_name = await SubjectRepository.get_subject_by_normalized_name(
            db=db,
            tenant_id=actor.tenant_id,
            normalized_name=normalized_name,
        )
        if existing_name:
            raise BadRequestException(detail="A subject with this name already exists.")

        code = normalize_subject_code(subject_data.code)
        if code:
            existing_code = await SubjectRepository.get_subject_by_normalized_code(
                db=db,
                tenant_id=actor.tenant_id,
                normalized_code=code,
            )
            if existing_code:
                raise BadRequestException(detail="A subject with this code already exists.")

        subject = Subject(
            tenant_id=actor.tenant_id,
            name=name,
            normalized_name=normalized_name,
            code=code,
            normalized_code=code,
            description=normalize_display_text(subject_data.description),
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
        if isinstance(actor, Teacher) and (
            not subject.is_active or subject.archived_at is not None
        ):
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
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
            lock=True,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")
        if subject.archived_at is not None:
            raise ConflictException("Archived subjects cannot be updated. Restore them first.")

        update_data = subject_data.model_dump(exclude_unset=True)
        target_name = subject.name
        target_normalized_name = subject.normalized_name
        target_code = subject.code
        target_normalized_code = subject.normalized_code

        if "name" in update_data:
            target_name, target_normalized_name = SubjectService._normalize_name(update_data["name"])
        if "code" in update_data:
            target_code = normalize_subject_code(update_data["code"])
            target_normalized_code = target_code

        identity_change = (
            target_normalized_name != subject.normalized_name
            or target_normalized_code != subject.normalized_code
        )
        if identity_change:
            dependencies = await SubjectRepository.count_dependencies(
                db=db,
                tenant_id=actor.tenant_id,
                subject_id=subject.id,
            )
            if SubjectService._has_any_usage(dependencies):
                raise ConflictException(
                    detail="Subject name and code are locked after the subject is first used.",
                    payload={"dependency_counts": dependencies},
                )

            if target_normalized_name != subject.normalized_name:
                existing_name = await SubjectRepository.get_subject_by_normalized_name(
                    db=db,
                    tenant_id=actor.tenant_id,
                    normalized_name=target_normalized_name,
                )
                if existing_name and existing_name.id != subject.id:
                    raise BadRequestException(detail="A subject with this name already exists.")

            if target_normalized_code and target_normalized_code != subject.normalized_code:
                existing_code = await SubjectRepository.get_subject_by_normalized_code(
                    db=db,
                    tenant_id=actor.tenant_id,
                    normalized_code=target_normalized_code,
                )
                if existing_code and existing_code.id != subject.id:
                    raise BadRequestException(detail="A subject with this code already exists.")

        if "name" in update_data:
            subject.name = target_name
            subject.normalized_name = target_normalized_name
        if "code" in update_data:
            subject.code = target_code
            subject.normalized_code = target_normalized_code
        if "description" in update_data:
            subject.description = normalize_display_text(update_data["description"])

        try:
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
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
            lock=True,
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
        return subject

    @staticmethod
    async def deactivate_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
            lock=True,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")
        if subject.archived_at is not None:
            raise ConflictException("Archived subjects cannot be deactivated. Restore them first.")
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
        return subject

    @staticmethod
    async def archive_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
            lock=True,
        )
        if subject is None:
            raise NotFoundException("Subject not found")
        if subject.archived_at is not None:
            return subject
        if subject.is_active:
            raise ConflictException("Deactivate the subject before archiving it.")

        await SubjectService._ensure_no_live_dependencies(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject.id,
        )
        subject.is_active = False
        subject.archived_at = datetime.now(timezone.utc)
        subject.archived_by_admin_id = actor.id
        await SubjectRepository.update_subject(db=db, subject=subject)
        await db.commit()
        return subject

    @staticmethod
    async def restore_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> Subject:
        SubjectService._ensure_tenant_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
            lock=True,
        )
        if subject is None:
            raise NotFoundException("Subject not found")
        if subject.archived_at is None:
            raise ConflictException("Only archived subjects can be restored.")

        subject.archived_at = None
        subject.archived_by_admin_id = None
        subject.is_active = False
        await SubjectRepository.update_subject(db=db, subject=subject)
        await db.commit()
        return subject

    @staticmethod
    async def hard_delete_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> SubjectResponse:
        """Permanently remove a never-used subject, regardless of current lifecycle state."""

        SubjectService._ensure_tenant_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
            lock=True,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")

        dependency_counts = await SubjectRepository.count_dependencies(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject.id,
        )
        if SubjectService._has_any_usage(dependency_counts):
            raise ConflictException(
                detail="This subject has already been used and cannot be permanently deleted.",
                payload={"dependency_counts": dependency_counts},
            )

        response = SubjectResponse.model_validate(subject)
        try:
            await SubjectRepository.delete_subject(db=db, subject=subject)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                detail="This subject became referenced and can no longer be permanently deleted."
            ) from exc
        return response
