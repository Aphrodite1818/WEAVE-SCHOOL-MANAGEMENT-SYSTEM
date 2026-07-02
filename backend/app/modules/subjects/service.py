import re
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.modules.subjects.models import Subject
from app.modules.subjects.repository import SubjectRepository
from app.modules.subjects.schemas import SubjectCreate, SubjectUpdate
from app.modules.teachers.models import Teacher, TeacherStatus
from app.modules.teachers.repository import TeacherRepository
from app.modules.tenant_admins.models import TenantAdmin


class SubjectService:
    """Business logic for tenant-configured subjects."""

    @staticmethod
    def _ensure_tenant_admin(actor: TenantAdmin) -> None:
        """Ensure the actor is a tenant admin."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant.")

    @staticmethod
    def _ensure_tenant_actor(actor: TenantAdmin | Teacher) -> None:
        """Ensure the actor is tenant-scoped."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Actor is not attached to a tenant.")

    @staticmethod
    def normalize_subject_name(value: str) -> str:
        """Normalize a display subject name for duplicate prevention."""

        return re.sub(r"\s+", " ", value.strip()).casefold()

    @staticmethod
    def normalize_subject_code(value: str | None) -> str | None:
        """Normalize subject codes for duplicate prevention."""

        if value is None:
            return None
        cleaned = re.sub(r"\s+", "", value.strip()).upper()
        return cleaned or None

    @staticmethod
    async def create_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_data: SubjectCreate,
    ) -> Subject:
        """Create subject."""

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
            code=subject_data.code.upper() if subject_data.code else None,
            normalized_code=normalized_code,
            description=subject_data.description,
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
        """Return subject."""

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
        return subject

    @staticmethod
    async def list_subjects(
        db: AsyncSession,
        actor: TenantAdmin | Teacher,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Subject], int]:
        """List subjects."""

        if not isinstance(actor, (TenantAdmin, Teacher)):
            raise ForbiddenException(detail="You are not allowed to view subjects.")
        SubjectService._ensure_tenant_actor(actor)
        limit = min(limit, 100)

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
        )

    @staticmethod
    async def update_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
        subject_data: SubjectUpdate,
    ) -> Subject:
        """Update subject."""

        SubjectService._ensure_tenant_admin(actor)

        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")

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
            update_data["code"] = update_data["code"].upper() if update_data["code"] else None

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
        """Activate subject."""

        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")

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
    async def deactivate_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> Subject:
        """Deactivate subject."""

        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")

        if not subject.is_active:
            return subject

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
    async def delete_subject(
        db: AsyncSession,
        actor: TenantAdmin,
        subject_id: UUID,
    ) -> None:
        """Delete subject."""

        SubjectService._ensure_tenant_admin(actor)
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            subject_id=subject_id,
        )
        if not subject:
            raise NotFoundException(detail="Subject not found.")

        await SubjectRepository.delete_subject(db=db, subject=subject)
        await db.commit()
