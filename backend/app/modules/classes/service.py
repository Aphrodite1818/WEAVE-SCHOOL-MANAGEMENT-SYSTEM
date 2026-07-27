import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.core.utils.normalization import normalized_class_arm_key, normalized_class_name_key
from app.modules.classes.models import ClassRoom
from app.modules.classes.repository import ClassRoomRepository
from app.modules.classes.schemas import (
    ClassRoomCreate,
    ClassRoomResponse,
    ClassRoomUpdate,
)
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.modules.students.repository import StudentParentLinkRepository
from app.modules.teachers.models import Teacher, TeacherAccountStatus, TeacherMembershipStatus
from app.modules.teachers.repository import TeacherMembershipRepository
from app.modules.tenant_admins.models import TenantAdmin


class ClassRoomService:
    """Business logic for classroom management."""

    @staticmethod
    def _ensure_tenant_admin(actor: TenantAdmin) -> None:
        """Ensure actor is a tenant admin."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant")

    @staticmethod
    def _ensure_tenant_actor(actor: TenantAdmin | Teacher | Student | Parent) -> None:
        """Ensure actor is attached to a tenant."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Actor is not attached to a tenant")

    @staticmethod
    async def _validate_teacher_assignment(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_membership_id: uuid.UUID | None,
    ) -> None:
        """Ensure an assigned class teacher exists and is active."""

        if teacher_membership_id is None:
            return

        teacher = await TeacherMembershipRepository.get_by_id(
            db,
            teacher_membership_id,
            tenant_id=tenant_id,
            load_account=True,
        )
        if teacher is None:
            raise NotFoundException("Teacher not found")
        if (
            teacher.status != TeacherMembershipStatus.ACTIVE
            or teacher.teacher_account.account_status != TeacherAccountStatus.ACTIVE
            or not teacher.teacher_account.is_active
        ):
            raise BadRequestException("Cannot assign an inactive teacher")

    @staticmethod
    def _build_classroom_model(
        *,
        tenant_id: uuid.UUID,
        payload: ClassRoomCreate,
    ) -> ClassRoom:
        """Build a normalized classroom model from a validated payload."""

        normalized_name = normalized_class_name_key(payload.name)
        if normalized_name is None:
            raise BadRequestException("Class name cannot be empty")

        return ClassRoom(
            tenant_id=tenant_id,
            name=payload.name,
            normalized_name=normalized_name,
            arm=payload.arm,
            normalized_arm=normalized_class_arm_key(payload.arm),
            teacher_membership_id=payload.teacher_membership_id,
            is_active=True,
            archived_at=None,
            archived_by_admin_id=None,
        )

    @staticmethod
    async def create_classroom(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ClassRoomCreate,
    ) -> ClassRoomResponse:
        """Create a tenant-scoped classroom."""

        ClassRoomService._ensure_tenant_admin(actor)

        existing_classroom = await ClassRoomRepository.get_by_normalized_name_and_arm(
            db=db,
            tenant_id=actor.tenant_id,
            class_name=payload.name,
            class_arm=payload.arm,
        )
        if existing_classroom is not None:
            raise BadRequestException("Classroom with this name and arm already exists")

        await ClassRoomService._validate_teacher_assignment(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_membership_id=payload.teacher_membership_id,
        )

        classroom = ClassRoomService._build_classroom_model(
            tenant_id=actor.tenant_id,
            payload=payload,
        )

        try:
            created_classroom = await ClassRoomRepository.add(
                db=db,
                classroom=classroom,
            )
            await db.commit()
            await db.refresh(created_classroom)
            return ClassRoomResponse.model_validate(created_classroom)
        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException(
                "Classroom creation failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def get_classroom_by_id(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Student | Parent,
        class_id: uuid.UUID,
    ) -> ClassRoomResponse:
        """Get classroom by ID with actor-based visibility rules."""

        ClassRoomService._ensure_tenant_actor(actor)

        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
        )
        if classroom is None:
            raise NotFoundException("Classroom not found")
        if not isinstance(actor, TenantAdmin) and classroom.archived_at is not None:
            raise NotFoundException("Classroom not found")

        if isinstance(actor, Teacher) and classroom.teacher_membership_id != actor.id:
            raise ForbiddenException("You do not have access to this classroom")

        if isinstance(actor, Student) and classroom.id != actor.class_id:
            raise ForbiddenException("You do not have access to this classroom")

        if isinstance(actor, Parent):
            links = await StudentParentLinkRepository.get_by_parent_id(
                db=db,
                tenant_id=actor.tenant_id,
                parent_id=actor.id,
            )
            linked_class_ids = {
                link.student.class_id
                for link in links
                if link.student is not None and link.student.class_id is not None
            }
            if classroom.id not in linked_class_ids:
                raise ForbiddenException("You do not have access to this classroom")

        return ClassRoomResponse.model_validate(classroom)

    @staticmethod
    async def get_all_classrooms(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Student | Parent,
        skip: int = 0,
        limit: int = 100,
        include_archived: bool = False,
    ) -> list[ClassRoomResponse]:
        """Get classrooms visible to the current actor."""

        ClassRoomService._ensure_tenant_actor(actor)
        limit = min(limit, 100)

        if isinstance(actor, TenantAdmin):
            classrooms = await ClassRoomRepository.list_for_tenant(
                db=db,
                tenant_id=actor.tenant_id,
                offset=skip,
                limit=limit,
                include_archived=include_archived,
            )
        elif isinstance(actor, Teacher):
            classrooms = await ClassRoomRepository.list_by_teacher_membership(
                db=db,
                tenant_id=actor.tenant_id,
                teacher_membership_id=actor.id,
            )
            classrooms = classrooms[skip : skip + limit]
        elif isinstance(actor, Student):
            classrooms = []
            if actor.class_id is not None:
                classroom = await ClassRoomRepository.get_by_id(
                    db=db,
                    tenant_id=actor.tenant_id,
                    class_id=actor.class_id,
                )
                if classroom is not None:
                    classrooms = [classroom]
        else:
            links = await StudentParentLinkRepository.get_by_parent_id(
                db=db,
                tenant_id=actor.tenant_id,
                parent_id=actor.id,
            )
            class_ids = list(
                {
                    link.student.class_id
                    for link in links
                    if link.student is not None and link.student.class_id is not None
                }
            )
            classrooms = await ClassRoomRepository.list_by_ids(
                db=db,
                tenant_id=actor.tenant_id,
                class_ids=class_ids,
            )
            classrooms = classrooms[skip : skip + limit]

        return [ClassRoomResponse.model_validate(classroom) for classroom in classrooms]

    @staticmethod
    async def get_active_classrooms(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Student | Parent,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ClassRoomResponse]:
        """Get active classrooms visible to the current actor."""

        classrooms = await ClassRoomService.get_all_classrooms(
            db=db,
            actor=actor,
            skip=skip,
            limit=limit,
        )
        return [classroom for classroom in classrooms if classroom.is_active]

    @staticmethod
    async def update_classroom(
        db: AsyncSession,
        actor: TenantAdmin,
        class_id: uuid.UUID,
        payload: ClassRoomUpdate,
    ) -> ClassRoomResponse:
        """Update classroom details."""

        ClassRoomService._ensure_tenant_admin(actor)

        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
        )
        if classroom is None:
            raise NotFoundException("Classroom not found")
        if classroom.archived_at is not None:
            raise ConflictException("Archived classrooms cannot be updated. Restore them first.")

        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)

        new_name = update_data.get("name", classroom.name)
        new_arm = update_data.get("arm", classroom.arm)
        new_normalized_name = normalized_class_name_key(new_name)
        if new_normalized_name is None:
            raise BadRequestException("Class name cannot be empty")
        new_normalized_arm = normalized_class_arm_key(new_arm)

        if (
            new_normalized_name != classroom.normalized_name
            or new_normalized_arm != classroom.normalized_arm
        ):
            existing_classroom = await ClassRoomRepository.get_by_normalized_name_and_arm(
                db=db,
                tenant_id=actor.tenant_id,
                class_name=new_name,
                class_arm=new_arm,
            )
            if existing_classroom is not None and existing_classroom.id != classroom.id:
                raise BadRequestException("Classroom with this name and arm already exists")

        if "teacher_membership_id" in update_data:
            await ClassRoomService._validate_teacher_assignment(
                db=db,
                tenant_id=actor.tenant_id,
                teacher_membership_id=update_data["teacher_membership_id"],
            )

        for field, value in update_data.items():
            setattr(classroom, field, value)

        classroom.normalized_name = new_normalized_name
        classroom.normalized_arm = new_normalized_arm

        try:
            updated_classroom = await ClassRoomRepository.save(
                db=db,
                classroom=classroom,
            )
            await db.commit()
            await db.refresh(updated_classroom)
            return ClassRoomResponse.model_validate(updated_classroom)
        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException(
                "Classroom update failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def deactivate_classroom(
        db: AsyncSession,
        actor: TenantAdmin,
        class_id: uuid.UUID,
    ) -> ClassRoomResponse:
        """Deactivate a classroom without archiving or deleting it."""

        ClassRoomService._ensure_tenant_admin(actor)

        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
        )
        if classroom is None:
            raise NotFoundException("Classroom not found")
        if classroom.archived_at is not None:
            raise ConflictException(
                "Archived records cannot be deactivated. Restore them first."
            )

        classroom.is_active = False
        await ClassRoomRepository.save(db, classroom)
        await db.commit()
        await db.refresh(classroom)
        return ClassRoomResponse.model_validate(classroom)

    @staticmethod
    async def activate_classroom(
        db: AsyncSession,
        actor: TenantAdmin,
        class_id: uuid.UUID,
    ) -> ClassRoomResponse:
        ClassRoomService._ensure_tenant_admin(actor)

        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
        )
        if classroom is None:
            raise NotFoundException("Classroom not found")
        if classroom.archived_at is not None:
            raise ConflictException("Archived classrooms must be restored before activation.")

        await ClassRoomService._validate_teacher_assignment(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_membership_id=classroom.teacher_membership_id,
        )

        if classroom.is_active:
            return ClassRoomResponse.model_validate(classroom)

        classroom.is_active = True
        classroom.archived_at = None
        classroom.archived_by_admin_id = None
        classroom = await ClassRoomRepository.save(db=db, classroom=classroom)
        await db.commit()
        await db.refresh(classroom)
        return ClassRoomResponse.model_validate(classroom)



    @staticmethod
    async def archive_classroom(
        db: AsyncSession,
        actor: TenantAdmin,
        class_id: uuid.UUID,
    ) -> ClassRoomResponse:
        ClassRoomService._ensure_tenant_admin(actor)

        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
        )


        if classroom is None:
            raise NotFoundException("Classroom not found")



        if classroom.archived_at is not None:
            return ClassRoomResponse.model_validate(classroom)


        classroom.is_active = False
        classroom.archived_at = datetime.now(timezone.utc)
        classroom.archived_by_admin_id = actor.id

        classroom = await ClassRoomRepository.save(
            db=db,
            classroom=classroom,
        )

        await db.commit()
        await db.refresh(classroom)
        return ClassRoomResponse.model_validate(classroom)







    @staticmethod
    async def restore_classroom(
        db: AsyncSession,
        actor: TenantAdmin,
        class_id: uuid.UUID,
    ) -> ClassRoomResponse:
        ClassRoomService._ensure_tenant_admin(actor)


        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
        )

        if classroom is None:
            raise NotFoundException("Classroom not found")

        if classroom.archived_at is None:
            return ClassRoomResponse.model_validate(classroom)

        classroom.archived_at = None
        classroom.archived_by_admin_id = None
        classroom.is_active = False


        classroom = await ClassRoomRepository.save(db=db, classroom=classroom)


        await db.commit()
        await db.refresh(classroom)
        return ClassRoomResponse.model_validate(classroom)
