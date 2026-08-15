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
from app.core.utils.normalization import (
    normalize_class_arm,
    normalize_display_text,
    normalized_class_arm_key,
    normalized_class_name_key,
)
from app.modules.classes.models import (
    AcademicCategory,
    AcademicLevel,
    ArmLabel,
    ClassRoom,
    Department,
)
from app.modules.classes.repository import (
    AcademicLevelRepository,
    ArmLabelRepository,
    ClassRoomRepository,
    DepartmentRepository,
)
from app.modules.classes.schemas import (
    AcademicLevelCreate,
    AcademicLevelResponse,
    AcademicLevelUpdate,
    ArmLabelCreate,
    ArmLabelResponse,
    ArmLabelUpdate,
    ClassRoomCreate,
    ClassRoomResponse,
    ClassRoomUpdate,
    DepartmentCreate,
    DepartmentResponse,
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
from app.tenant_management.models import InstitutionType
from app.tenant_management.repository import TenantRepository


ALLOWED_CATEGORIES: dict[InstitutionType, tuple[AcademicCategory, ...]] = {
    InstitutionType.PRIMARY_SCHOOL: (
        AcademicCategory.KINDERGARTEN,
        AcademicCategory.PRIMARY,
    ),
    InstitutionType.SECONDARY_SCHOOL: (
        AcademicCategory.JUNIOR_SECONDARY,
        AcademicCategory.SENIOR_SECONDARY,
    ),
}


class AcademicLevelService:
    @staticmethod
    def _ensure_admin(actor: TenantAdmin) -> None:
        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant")

    @staticmethod
    async def _validate_category(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        category: AcademicCategory,
    ) -> None:
        tenant = await TenantRepository.get_by_id(db, tenant_id)
        if tenant is None:
            raise NotFoundException("Tenant not found")
        if tenant.institution_type is None:
            raise ConflictException(
                "Choose the institution type during onboarding before creating academic levels."
            )
        if category not in ALLOWED_CATEGORIES[tenant.institution_type]:
            raise BadRequestException(
                f"{category.value} is not valid for {tenant.institution_type.value}."
            )

    @staticmethod
    async def create(
        db: AsyncSession, actor: TenantAdmin, payload: AcademicLevelCreate
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        await AcademicLevelService._validate_category(
            db, tenant_id=actor.tenant_id, category=payload.category
        )
        if await AcademicLevelRepository.get_by_normalized_name(db, actor.tenant_id, payload.name):
            raise ConflictException("Academic level with this name already exists")
        if await AcademicLevelRepository.get_by_category_position(
            db, actor.tenant_id, payload.category, payload.position
        ):
            raise ConflictException("Another academic level already uses this category position")
        level = AcademicLevel(
            tenant_id=actor.tenant_id,
            name=payload.name,
            normalized_name=normalized_class_name_key(payload.name),
            category=payload.category,
            position=payload.position,
            specialization_required_from_term_position=(
                payload.specialization_required_from_term_position
            ),
            is_active=True,
        )
        try:
            await AcademicLevelRepository.add(db, level)
            await db.commit()
            await db.refresh(level)
            return AcademicLevelResponse.model_validate(level)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "Academic level name and category position must be unique"
            ) from exc

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
        target_category = payload.category or level.category
        target_position = payload.position or level.position
        if payload.category is not None:
            await AcademicLevelService._validate_category(
                db, tenant_id=actor.tenant_id, category=payload.category
            )
        position_owner = await AcademicLevelRepository.get_by_category_position(
            db,
            actor.tenant_id,
            target_category,
            target_position,
            exclude_id=level.id,
        )
        if position_owner is not None:
            raise ConflictException("Another academic level already uses this category position")
        level.category = target_category
        level.position = target_position
        if "specialization_required_from_term_position" in payload.model_fields_set:
            level.specialization_required_from_term_position = (
                payload.specialization_required_from_term_position
            )
        await AcademicLevelRepository.save(db, level)
        await db.commit()
        await db.refresh(level)
        return AcademicLevelResponse.model_validate(level)

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


class DepartmentService:
    @staticmethod
    async def create(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: DepartmentCreate,
    ) -> DepartmentResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        name = normalize_display_text(payload.name)
        if name is None:
            raise BadRequestException("Department name is required")
        normalized_name = name.casefold()
        if await DepartmentRepository.get_by_normalized_name(
            db, actor.tenant_id, normalized_name
        ):
            raise ConflictException("Department with this name already exists")
        department = Department(
            tenant_id=actor.tenant_id,
            name=name,
            normalized_name=normalized_name,
            is_active=True,
        )
        try:
            await DepartmentRepository.add(db, department)
            await db.commit()
            await db.refresh(department)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("Department with this name already exists") from exc
        return DepartmentResponse.model_validate(department)

    @staticmethod
    async def list(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Student | Parent,
        *,
        active_only: bool = False,
    ) -> list[DepartmentResponse]:
        if not actor.tenant_id:
            raise ForbiddenException("Actor is not attached to a tenant")
        rows = await DepartmentRepository.list_for_tenant(
            db, actor.tenant_id, active_only=active_only
        )
        return [DepartmentResponse.model_validate(row) for row in rows]


class ArmLabelService:
    @staticmethod
    def _clean_label(value: str) -> tuple[str, str]:
        label = normalize_class_arm(value)
        if label is None:
            raise BadRequestException("Arm label is required")
        return label, normalized_class_arm_key(label)

    @staticmethod
    async def create(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: ArmLabelCreate,
    ) -> ArmLabelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        label, normalized_label = ArmLabelService._clean_label(payload.label)
        if await ArmLabelRepository.get_by_normalized_label(
            db, actor.tenant_id, normalized_label
        ):
            raise ConflictException("Arm label with this name already exists")
        arm_label = ArmLabel(
            tenant_id=actor.tenant_id,
            label=label,
            normalized_label=normalized_label,
            position=payload.position,
            is_active=True,
        )
        try:
            await ArmLabelRepository.add(db, arm_label)
            await db.commit()
            await db.refresh(arm_label)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("Arm label with this name already exists") from exc
        return ArmLabelResponse.model_validate(arm_label)

    @staticmethod
    async def list(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Student | Parent,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> list[ArmLabelResponse]:
        if not actor.tenant_id:
            raise ForbiddenException("Actor is not attached to a tenant")
        rows = await ArmLabelRepository.list_for_tenant(
            db,
            actor.tenant_id,
            active_only=active_only,
            include_archived=include_archived and isinstance(actor, TenantAdmin),
        )
        return [ArmLabelResponse.model_validate(row) for row in rows]

    @staticmethod
    async def update(
        db: AsyncSession,
        actor: TenantAdmin,
        arm_label_id: uuid.UUID,
        payload: ArmLabelUpdate,
    ) -> ArmLabelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        arm_label = await ArmLabelRepository.get_by_id(
            db,
            actor.tenant_id,
            arm_label_id,
            lock=True,
        )
        if arm_label is None:
            raise NotFoundException("Arm label not found")
        if arm_label.archived_at is not None:
            raise ConflictException("Archived arm labels cannot be updated")
        if payload.label is not None:
            label, normalized_label = ArmLabelService._clean_label(payload.label)
            existing = await ArmLabelRepository.get_by_normalized_label(
                db,
                actor.tenant_id,
                normalized_label,
            )
            if existing is not None and existing.id != arm_label.id:
                raise ConflictException("Arm label with this name already exists")
            arm_label.label = label
            arm_label.normalized_label = normalized_label
        if "position" in payload.model_fields_set:
            arm_label.position = payload.position
        if payload.is_active is not None:
            arm_label.is_active = payload.is_active
        await ArmLabelRepository.save(db, arm_label)
        await db.commit()
        await db.refresh(arm_label)
        return ArmLabelResponse.model_validate(arm_label)

    @staticmethod
    async def archive(
        db: AsyncSession,
        actor: TenantAdmin,
        arm_label_id: uuid.UUID,
    ) -> ArmLabelResponse:
        AcademicLevelService._ensure_admin(actor)
        arm_label = await ArmLabelRepository.get_by_id(
            db,
            actor.tenant_id,
            arm_label_id,
            lock=True,
        )
        if arm_label is None:
            raise NotFoundException("Arm label not found")
        dependency_count = await ArmLabelRepository.count_class_dependencies(
            db,
            actor.tenant_id,
            arm_label.id,
        )
        if dependency_count:
            raise ConflictException(
                "Arm label is used by classes and cannot be archived.",
                payload={"dependency_counts": {"classes": dependency_count}},
            )
        arm_label.is_active = False
        arm_label.archived_at = datetime.now(timezone.utc)
        await ArmLabelRepository.save(db, arm_label)
        await db.commit()
        await db.refresh(arm_label)
        return ArmLabelResponse.model_validate(arm_label)


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
    async def _validate_arm_label(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        arm_label_id: uuid.UUID | None,
    ) -> None:
        if arm_label_id is None:
            return
        arm_label = await ArmLabelRepository.get_by_id(db, tenant_id, arm_label_id)
        if (
            arm_label is None
            or not arm_label.is_active
            or arm_label.archived_at is not None
        ):
            raise BadRequestException("Arm label must be active and belong to this tenant")

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
            department_id=payload.department_id,
            arm_label_id=payload.arm_label_id,
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
        if payload.department_id is not None:
            department = await DepartmentRepository.get_by_id(
                db, actor.tenant_id, payload.department_id
            )
            if department is None or not department.is_active or department.archived_at is not None:
                raise BadRequestException("Department must be active and belong to this tenant")
        await ClassRoomService._validate_arm_label(
            db,
            tenant_id=actor.tenant_id,
            arm_label_id=payload.arm_label_id,
        )

        existing_classroom = await ClassRoomRepository.get_by_level_department_arm_label(
            db=db,
            tenant_id=actor.tenant_id,
            academic_level_id=payload.academic_level_id,
            department_id=payload.department_id,
            arm_label_id=payload.arm_label_id,
        )
        if existing_classroom is not None:
            raise BadRequestException("Classroom with this level, department, and arm already exists")

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
            reloaded = await ClassRoomRepository.get_by_id(
                db,
                actor.tenant_id,
                created_classroom.id,
            )
            return ClassRoomResponse.model_validate(reloaded or created_classroom)
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
        if "department_id" in payload.model_fields_set:
            update_data["department_id"] = payload.department_id
        if "arm_label_id" in payload.model_fields_set:
            update_data["arm_label_id"] = payload.arm_label_id

        new_level_id = update_data.get("academic_level_id", classroom.academic_level_id)
        new_arm_label_id = update_data.get("arm_label_id", classroom.arm_label_id)
        new_department_id = update_data.get("department_id", classroom.department_id)

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
        if new_department_id is not None:
            department = await DepartmentRepository.get_by_id(
                db, actor.tenant_id, new_department_id
            )
            if department is None or not department.is_active or department.archived_at is not None:
                raise BadRequestException("Department must be active and belong to this tenant")
        await ClassRoomService._validate_arm_label(
            db,
            tenant_id=actor.tenant_id,
            arm_label_id=new_arm_label_id,
        )

        if (
            new_level_id != classroom.academic_level_id
            or new_department_id != classroom.department_id
            or new_arm_label_id != classroom.arm_label_id
        ):
            existing_classroom = await ClassRoomRepository.get_by_level_department_arm_label(
                db=db,
                tenant_id=actor.tenant_id,
                academic_level_id=new_level_id,
                department_id=new_department_id,
                arm_label_id=new_arm_label_id,
            )
            if existing_classroom is not None and existing_classroom.id != classroom.id:
                raise BadRequestException(
                    "Classroom with this level, department, and arm already exists"
                )

        if "teacher_membership_id" in update_data:
            await ClassRoomService._validate_teacher_assignment(
                db=db,
                tenant_id=actor.tenant_id,
                teacher_membership_id=update_data["teacher_membership_id"],
            )

        for field, value in update_data.items():
            setattr(classroom, field, value)

        try:
            updated_classroom = await ClassRoomRepository.save(
                db=db,
                classroom=classroom,
            )
            await db.commit()
            await db.refresh(updated_classroom)
            reloaded = await ClassRoomRepository.get_by_id(
                db,
                actor.tenant_id,
                updated_classroom.id,
            )
            return ClassRoomResponse.model_validate(reloaded or updated_classroom)
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
