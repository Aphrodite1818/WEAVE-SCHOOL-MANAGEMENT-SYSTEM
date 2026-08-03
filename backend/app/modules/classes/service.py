import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.core.utils.normalization import normalized_class_arm_key, normalized_class_name_key
from app.modules.classes.models import ClassRoom
from app.modules.classes.repository import ClassRoomRepository
from app.modules.classes.schemas import (
    ClassProgressionClearRequest,
    ClassProgressionConfigureRequest,
    ClassProgressionResponse,
    ClassRoomCreate,
    ClassRoomResponse,
    ClassRoomUpdate,
)
from app.modules.parents.models import Parent
from app.modules.students.models import AcademicStatus, Student
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
    def _build_progression_response(
        classroom: ClassRoom,
        next_classroom: ClassRoom | None = None,
    ) -> ClassProgressionResponse:
        return ClassProgressionResponse(
            class_id=classroom.id,
            class_name=classroom.name,
            class_arm=classroom.arm,
            next_class_id=classroom.next_class_id,
            next_class_name=next_classroom.name if next_classroom is not None else None,
            next_class_arm=next_classroom.arm if next_classroom is not None else None,
            is_terminal=classroom.is_terminal,
            is_active=classroom.is_active,
        )

    @staticmethod
    async def _ensure_no_progression_cycle(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        next_class_id: uuid.UUID,
    ) -> None:
        current_id: uuid.UUID | None = next_class_id
        visited: set[uuid.UUID] = set()

        while current_id is not None:
            if current_id == class_id:
                raise BadRequestException("Class progression cannot create a circular chain")
            if current_id in visited:
                raise BadRequestException("Existing class progression contains a circular chain")
            visited.add(current_id)

            current = await ClassRoomRepository.get_by_id(
                db=db,
                tenant_id=tenant_id,
                class_id=current_id,
            )
            if current is None:
                return
            current_id = current.next_class_id

    @staticmethod
    async def configure_class_progression(
        db: AsyncSession,
        actor: TenantAdmin,
        class_id: uuid.UUID,
        payload: ClassProgressionConfigureRequest,
    ) -> ClassProgressionResponse:
        """Configure the next class or terminal state used by student progression."""

        ClassRoomService._ensure_tenant_admin(actor)

        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
        )
        if classroom is None:
            raise NotFoundException("Classroom not found")
        if classroom.archived_at is not None:
            raise ConflictException("Archived classrooms cannot be configured. Restore them first.")

        next_classroom: ClassRoom | None = None
        if payload.next_class_id is not None:
            if payload.next_class_id == classroom.id:
                raise BadRequestException("A class cannot progress to itself")
            next_classroom = await ClassRoomRepository.get_by_id(
                db=db,
                tenant_id=actor.tenant_id,
                class_id=payload.next_class_id,
            )
            if next_classroom is None:
                raise NotFoundException("Next class not found")
            if not next_classroom.is_active or next_classroom.archived_at is not None:
                raise BadRequestException("Next class must be active")
            await ClassRoomService._ensure_no_progression_cycle(
                db=db,
                tenant_id=actor.tenant_id,
                class_id=classroom.id,
                next_class_id=next_classroom.id,
            )

        classroom.next_class_id = None if payload.is_terminal else payload.next_class_id
        classroom.is_terminal = payload.is_terminal

        try:
            updated_classroom = await ClassRoomRepository.save(
                db=db,
                classroom=classroom,
            )
            await db.commit()
            await db.refresh(updated_classroom)
            return ClassRoomService._build_progression_response(
                updated_classroom,
                None if updated_classroom.is_terminal else next_classroom,
            )
        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException("Class progression configuration is invalid.") from exc

    @staticmethod
    async def clear_class_progression(
        db: AsyncSession,
        actor: TenantAdmin,
        class_id: uuid.UUID,
        payload: ClassProgressionClearRequest,
    ) -> ClassProgressionResponse:
        """Clear the next class and terminal state for a classroom."""

        ClassRoomService._ensure_tenant_admin(actor)
        _ = payload.confirmation

        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
        )
        if classroom is None:
            raise NotFoundException("Classroom not found")
        if classroom.archived_at is not None:
            raise ConflictException("Archived classrooms cannot be configured. Restore them first.")

        classroom.next_class_id = None
        classroom.is_terminal = False

        updated_classroom = await ClassRoomRepository.save(db=db, classroom=classroom)
        await db.commit()
        await db.refresh(updated_classroom)
        return ClassRoomService._build_progression_response(updated_classroom)

    @staticmethod
    async def _ensure_no_live_dependencies(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> None:
        active_students = await ClassRoomRepository.count_assigned_students_by_status(
            db,
            tenant_id,
            class_id,
            AcademicStatus.ACTIVE,
        )
        if active_students > 0:
            raise ConflictException(
                "This class still has active students. Move or resolve all students before deactivating the class."
            )

        suspended_students = await ClassRoomRepository.count_assigned_students_by_status(
            db,
            tenant_id,
            class_id,
            AcademicStatus.SUSPENDED,
        )
        if suspended_students > 0:
            raise ConflictException(
                "This class still has suspended students assigned to it. Move or resolve all suspended students before deactivating the class."
            )

        current_enrollments = await ClassRoomRepository.count_current_enrollments(
            db,
            tenant_id,
            class_id,
        )
        if current_enrollments > 0:
            raise ConflictException(
                "This class still has current student enrollments. End or move all current enrollments before deactivating the class."
            )

        active_mappings = await ClassRoomRepository.count_active_class_subjects(
            db,
            tenant_id,
            class_id,
        )
        if active_mappings > 0:
            raise ConflictException(
                "This class still has active subject mappings. Deactivate or archive all class-subject mappings before deactivating the class."
            )

        active_assignments = await ClassRoomRepository.count_active_teacher_assignments(
            db,
            tenant_id,
            class_id,
        )
        if active_assignments > 0:
            raise ConflictException(
                "This class still has active teacher assignments. End all active teacher assignments before deactivating the class."
            )

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
            raise ConflictException("Archived records cannot be deactivated. Restore them first.")
        if not classroom.is_active:
            return ClassRoomResponse.model_validate(classroom)

        await ClassRoomService._ensure_no_live_dependencies(
            db,
            tenant_id=actor.tenant_id,
            class_id=classroom.id,
        )

        classroom.is_active = False
        await ClassRoomRepository.save(db, classroom)
        await db.commit()
        await db.refresh(classroom)
        return ClassRoomResponse.model_validate(classroom)

    @staticmethod
    async def purge_setup_classroom(
        db: AsyncSession,
        actor: TenantAdmin,
        class_id: uuid.UUID,
    ) -> ClassRoomResponse:
        """Permanently remove an unused classroom created during assisted setup."""

        ClassRoomService._ensure_tenant_admin(actor)

        classroom = await ClassRoomRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=class_id,
        )
        if classroom is None:
            raise NotFoundException("Classroom not found")

        dependency_counts = await ClassRoomRepository.count_class_dependencies(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=classroom.id,
        )
        if any(count > 0 for count in dependency_counts.values()):
            raise ConflictException(
                detail="This class is already referenced and cannot be removed from setup.",
                payload={"dependency_counts": dependency_counts},
            )

        response = ClassRoomResponse.model_validate(classroom)
        await ClassRoomRepository.clear_next_class_references(
            db=db,
            tenant_id=actor.tenant_id,
            class_id=classroom.id,
        )
        await ClassRoomRepository.delete_classroom(db=db, classroom=classroom)
        await db.commit()
        return response

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
        if classroom.is_active:
            raise ConflictException(
                "Active classes cannot be archived. Deactivate the class first."
            )

        await ClassRoomService._ensure_no_live_dependencies(
            db,
            tenant_id=actor.tenant_id,
            class_id=classroom.id,
        )

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
