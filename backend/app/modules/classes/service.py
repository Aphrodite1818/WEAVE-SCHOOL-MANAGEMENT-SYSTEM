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
from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelProgressionMode,
    ClassRoom,
    ProgressionSelectionOption,
    ProgressionSelectionTargetType,
)
from app.modules.classes.repository import AcademicLevelRepository, ClassRoomRepository
from app.modules.classes.schemas import (
    AcademicLevelCreate,
    AcademicLevelProgressionConfigureRequest,
    AcademicLevelProgressionResponse,
    AcademicLevelResponse,
    AcademicLevelUpdate,
    ClassRoomCreate,
    ClassRoomResponse,
    ClassRoomUpdate,
)
from app.modules.parents.models import Parent
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.students.models import AcademicStatus, Student
from app.modules.students.repository import StudentParentLinkRepository
from app.modules.teachers.models import (
    Teacher,
    TeacherAccountStatus,
    TeacherMembershipStatus,
)
from app.modules.teachers.repository import TeacherMembershipRepository
from app.modules.tenant_admins.models import TenantAdmin


class AcademicLevelService:
    @staticmethod
    def _ensure_admin(actor: TenantAdmin) -> None:
        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant")

    @staticmethod
    async def _ensure_progression_remains_acyclic(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        source_level_id: uuid.UUID,
        proposed_target_level_ids: set[uuid.UUID],
    ) -> None:
        levels = await AcademicLevelRepository.list_for_tenant(
            db, tenant_id, include_archived=True
        )
        adjacency: dict[uuid.UUID, set[uuid.UUID]] = {
            level.id: ({level.next_level_id} if level.next_level_id else set())
            for level in levels
        }
        for source_id, target_id in await AcademicLevelRepository.list_progression_edges(
            db, tenant_id
        ):
            adjacency.setdefault(source_id, set()).add(target_id)
        adjacency[source_level_id] = proposed_target_level_ids

        pending = list(proposed_target_level_ids)
        visited: set[uuid.UUID] = set()
        while pending:
            current = pending.pop()
            if current == source_level_id:
                raise BadRequestException("Academic level progression cannot be circular")
            if current in visited:
                continue
            visited.add(current)
            pending.extend(adjacency.get(current, set()))

    @staticmethod
    async def create(
        db: AsyncSession, actor: TenantAdmin, payload: AcademicLevelCreate
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        if await AcademicLevelRepository.get_by_normalized_name(db, actor.tenant_id, payload.name):
            raise ConflictException("Academic level with this name already exists")
        level = AcademicLevel(
            tenant_id=actor.tenant_id,
            name=payload.name,
            normalized_name=normalized_class_name_key(payload.name),
            is_active=True,
        )
        try:
            await AcademicLevelRepository.add(db, level)
            await db.commit()
            await db.refresh(level)
            return AcademicLevelResponse.model_validate(level)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("Academic level with this name already exists") from exc

    @staticmethod
    async def list(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Student | Parent,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> list[AcademicLevelResponse]:
        if not actor.tenant_id:
            raise ForbiddenException(detail="Actor is not attached to a tenant")
        levels = await AcademicLevelRepository.list_for_tenant(
            db,
            actor.tenant_id,
            active_only=active_only,
            include_archived=include_archived and isinstance(actor, TenantAdmin),
        )
        return [AcademicLevelResponse.model_validate(level) for level in levels]

    @staticmethod
    async def update(
        db: AsyncSession,
        actor: TenantAdmin,
        academic_level_id: uuid.UUID,
        payload: AcademicLevelUpdate,
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(db, actor.tenant_id, academic_level_id)
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.archived_at is not None:
            raise ConflictException("Archived academic levels cannot be updated")
        if payload.name is not None:
            existing = await AcademicLevelRepository.get_by_normalized_name(
                db, actor.tenant_id, payload.name
            )
            if existing is not None and existing.id != level.id:
                raise ConflictException("Academic level with this name already exists")
            level.name = payload.name
            level.normalized_name = normalized_class_name_key(payload.name)
        await AcademicLevelRepository.save(db, level)
        await db.commit()
        await db.refresh(level)
        return AcademicLevelResponse.model_validate(level)

    @staticmethod
    async def configure_progression(
        db: AsyncSession,
        actor: TenantAdmin,
        academic_level_id: uuid.UUID,
        payload: AcademicLevelProgressionConfigureRequest,
    ) -> AcademicLevelProgressionResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(db, actor.tenant_id, academic_level_id)
        if level is None:
            raise NotFoundException("Academic level not found")
        next_level = None
        if payload.next_level_id is not None:
            if payload.next_level_id == level.id:
                raise BadRequestException("An academic level cannot progress to itself")
            next_level = await AcademicLevelRepository.get_by_id(
                db, actor.tenant_id, payload.next_level_id
            )
            if next_level is None:
                raise NotFoundException("Next academic level not found")
            visited = {level.id}
            cursor = next_level
            while cursor is not None:
                if cursor.id in visited:
                    raise BadRequestException("Academic level progression cannot be circular")
                visited.add(cursor.id)
                cursor = (
                    await AcademicLevelRepository.get_by_id(
                        db, actor.tenant_id, cursor.next_level_id
                    )
                    if cursor.next_level_id
                    else None
                )
        options: list[ProgressionSelectionOption] = []
        proposed_target_level_ids: set[uuid.UUID] = (
            {payload.next_level_id} if payload.next_level_id else set()
        )
        if payload.progression_mode == AcademicLevelProgressionMode.STUDENT_SELECTION:
            if payload.selection_target_type == ProgressionSelectionTargetType.LEVEL:
                for target_id in payload.target_level_ids:
                    if target_id == level.id:
                        raise BadRequestException("An academic level cannot select itself")
                    target = await AcademicLevelRepository.get_by_id(
                        db, actor.tenant_id, target_id
                    )
                    if target is None:
                        raise NotFoundException("Selection target academic level not found")
                    if not target.is_active or target.archived_at is not None:
                        raise ConflictException("Selection target academic level is inactive")
                    visited = {level.id}
                    cursor = target
                    while cursor is not None:
                        if cursor.id in visited:
                            raise BadRequestException(
                                "Academic level progression cannot be circular"
                            )
                        visited.add(cursor.id)
                        cursor = (
                            await AcademicLevelRepository.get_by_id(
                                db, actor.tenant_id, cursor.next_level_id
                            )
                            if cursor.next_level_id
                            else None
                        )
                    options.append(
                        ProgressionSelectionOption(
                            tenant_id=actor.tenant_id,
                            source_level_id=level.id,
                            target_level_id=target.id,
                        )
                    )
                    proposed_target_level_ids.add(target.id)
            else:
                for target_id in payload.target_classroom_ids:
                    target_class = await ClassRoomRepository.get_by_id(
                        db, actor.tenant_id, target_id
                    )
                    if target_class is None:
                        raise NotFoundException("Selection target classroom not found")
                    if not target_class.is_active or target_class.archived_at is not None:
                        raise ConflictException("Selection target classroom is inactive")
                    if target_class.academic_level_id == level.id:
                        raise BadRequestException(
                            "A progression destination cannot belong to its source level"
                        )
                    target_level = await AcademicLevelRepository.get_by_id(
                        db, actor.tenant_id, target_class.academic_level_id
                    )
                    if target_level is None or not target_level.is_active or target_level.archived_at:
                        raise ConflictException("Selection target classroom has no active level")
                    options.append(
                        ProgressionSelectionOption(
                            tenant_id=actor.tenant_id,
                            source_level_id=level.id,
                            target_classroom_id=target_class.id,
                        )
                    )
                    proposed_target_level_ids.add(target_class.academic_level_id)

        await AcademicLevelService._ensure_progression_remains_acyclic(
            db,
            tenant_id=actor.tenant_id,
            source_level_id=level.id,
            proposed_target_level_ids=proposed_target_level_ids,
        )

        level.progression_mode = payload.progression_mode
        level.next_level_id = payload.next_level_id
        level.selection_target_type = payload.selection_target_type
        await AcademicLevelRepository.save(db, level)
        await AcademicLevelRepository.replace_progression_options(
            db, actor.tenant_id, level.id, options
        )
        await db.commit()
        await db.refresh(level)
        return AcademicLevelProgressionResponse(
            academic_level_id=level.id,
            academic_level_name=level.name,
            next_level_id=level.next_level_id,
            next_level_name=next_level.name if next_level else None,
            progression_mode=level.progression_mode,
            selection_target_type=level.selection_target_type,
            target_level_ids=[option.target_level_id for option in options if option.target_level_id],
            target_classroom_ids=[
                option.target_classroom_id for option in options if option.target_classroom_id
            ],
            is_active=level.is_active,
        )

    @staticmethod
    async def get_progression(
        db: AsyncSession,
        actor: TenantAdmin,
        academic_level_id: uuid.UUID,
    ) -> AcademicLevelProgressionResponse:
        AcademicLevelService._ensure_admin(actor)
        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, academic_level_id
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        options = await AcademicLevelRepository.list_progression_options(
            db, actor.tenant_id, level.id
        )
        next_level = (
            await AcademicLevelRepository.get_by_id(db, actor.tenant_id, level.next_level_id)
            if level.next_level_id
            else None
        )
        return AcademicLevelProgressionResponse(
            academic_level_id=level.id,
            academic_level_name=level.name,
            next_level_id=level.next_level_id,
            next_level_name=next_level.name if next_level else None,
            progression_mode=level.progression_mode,
            selection_target_type=level.selection_target_type,
            target_level_ids=[option.target_level_id for option in options if option.target_level_id],
            target_classroom_ids=[
                option.target_classroom_id for option in options if option.target_classroom_id
            ],
            is_active=level.is_active,
        )

    @staticmethod
    async def purge_setup_level(
        db: AsyncSession,
        actor: TenantAdmin,
        academic_level_id: uuid.UUID,
    ) -> AcademicLevelResponse:
        """Permanently remove an unused academic level during assisted setup."""

        AcademicLevelService._ensure_admin(actor)
        level = await AcademicLevelRepository.get_by_id(
            db,
            actor.tenant_id,
            academic_level_id,
            lock=True,
        )
        if level is None:
            raise NotFoundException("Academic level not found")

        dependency_counts = await AcademicLevelRepository.count_setup_dependencies(
            db,
            actor.tenant_id,
            academic_level_id,
        )
        if any(count > 0 for count in dependency_counts.values()):
            raise ConflictException(
                detail=(
                    "This academic level has class arms or other references and cannot "
                    "be removed from setup."
                ),
                payload={"dependency_counts": dependency_counts},
            )

        response = AcademicLevelResponse.model_validate(level)
        await AcademicLevelRepository.delete(db, level)
        await db.commit()
        return response


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

        return ClassRoom(
            tenant_id=tenant_id,
            academic_level_id=payload.academic_level_id,
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
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, payload.academic_level_id
        )
        if level is None or level.archived_at is not None or not level.is_active:
            raise BadRequestException("Academic level must be active and belong to this tenant")

        existing_classroom = await ClassRoomRepository.get_by_level_and_arm(
            db=db,
            tenant_id=actor.tenant_id,
            academic_level_id=payload.academic_level_id,
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
        limit = min(limit, 500)

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
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

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
        if "teacher_membership_id" in payload.model_fields_set:
            update_data["teacher_membership_id"] = payload.teacher_membership_id

        new_level_id = update_data.get("academic_level_id", classroom.academic_level_id)
        new_arm = update_data.get("arm", classroom.arm)
        new_normalized_arm = normalized_class_arm_key(new_arm)

        if new_level_id != classroom.academic_level_id:
            dependency_counts = await ClassRoomRepository.count_class_dependencies(
                db=db,
                tenant_id=actor.tenant_id,
                class_id=classroom.id,
            )
            if any(dependency_counts.values()):
                raise ConflictException(
                    "Academic level cannot be changed after this class has academic history.",
                    payload={"dependency_counts": dependency_counts},
                )

        level = await AcademicLevelRepository.get_by_id(db, actor.tenant_id, new_level_id)
        if level is None or level.archived_at is not None or not level.is_active:
            raise BadRequestException("Academic level must be active and belong to this tenant")

        if (
            new_level_id != classroom.academic_level_id
            or new_normalized_arm != classroom.normalized_arm
        ):
            existing_classroom = await ClassRoomRepository.get_by_level_and_arm(
                db=db,
                tenant_id=actor.tenant_id,
                academic_level_id=new_level_id,
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
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

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
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

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
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

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
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

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
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

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
