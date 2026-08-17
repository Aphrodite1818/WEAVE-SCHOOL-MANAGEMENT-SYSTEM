"""Business services for the level-owned academic structure."""

from __future__ import annotations

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
from app.modules.classes.category_catalog import (
    categories_for,
    category_definition,
    category_supports_departments,
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
    AcademicCategoryOption,
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
from app.modules.teachers.models import Teacher, TeacherAccountStatus, TeacherMembershipStatus
from app.modules.teachers.repository import TeacherMembershipRepository
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository


async def _tenant_institution_type(db: AsyncSession, tenant_id: uuid.UUID):
    tenant = await TenantRepository.get_by_id(db, tenant_id)
    if tenant is None:
        raise NotFoundException("Tenant not found")
    if tenant.institution_type is None:
        raise ConflictException("Choose the institution type before configuring academics.")
    return tenant.institution_type


class AcademicLevelService:
    @staticmethod
    def _ensure_admin(actor: TenantAdmin) -> None:
        if not actor.tenant_id:
            raise ForbiddenException("Tenant admin is not attached to a tenant")

    @staticmethod
    async def category_options(db: AsyncSession, actor) -> list[AcademicCategoryOption]:
        institution_type = await _tenant_institution_type(db, actor.tenant_id)
        return [
            AcademicCategoryOption(
                value=item.value,
                label=item.label,
                position=item.position,
                supports_departments=item.supports_departments,
            )
            for item in categories_for(institution_type)
        ]

    @staticmethod
    async def _validate_category(
        db: AsyncSession, tenant_id: uuid.UUID, category: AcademicCategory
    ) -> None:
        institution_type = await _tenant_institution_type(db, tenant_id)
        if category_definition(institution_type, category) is None:
            raise BadRequestException(f"{category.value} is not valid for this institution type.")

    @staticmethod
    async def create(
        db: AsyncSession, actor: TenantAdmin, payload: AcademicLevelCreate
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        await AcademicLevelService._validate_category(db, actor.tenant_id, payload.category)
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
            is_active=True,
        )
        try:
            await AcademicLevelRepository.add(db, level)
            await db.commit()
            await db.refresh(level)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("Academic level name and position must be unique") from exc
        return AcademicLevelResponse.model_validate(level)

    @staticmethod
    async def list(db: AsyncSession, actor, *, active_only=False, include_archived=False):
        if not actor.tenant_id:
            raise ForbiddenException("Actor is not attached to a tenant")
        rows = await AcademicLevelRepository.list_for_tenant(
            db,
            actor.tenant_id,
            active_only=active_only,
            include_archived=include_archived and isinstance(actor, TenantAdmin),
        )
        return [AcademicLevelResponse.model_validate(row) for row in rows]

    @staticmethod
    async def update(
        db: AsyncSession,
        actor: TenantAdmin,
        academic_level_id: uuid.UUID,
        payload: AcademicLevelUpdate,
    ):
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, academic_level_id, lock=True
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.archived_at:
            raise ConflictException("Archived academic levels cannot be updated")
        data = payload.model_dump(exclude_unset=True)
        if "category" in data:
            await AcademicLevelService._validate_category(db, actor.tenant_id, data["category"])
        target_category = data.get("category", level.category)
        target_position = data.get("position", level.position)
        owner = await AcademicLevelRepository.get_by_category_position(
            db, actor.tenant_id, target_category, target_position, exclude_id=level.id
        )
        if owner:
            raise ConflictException("Another academic level already uses this category position")
        if "name" in data:
            existing = await AcademicLevelRepository.get_by_normalized_name(
                db, actor.tenant_id, data["name"]
            )
            if existing and existing.id != level.id:
                raise ConflictException("Academic level with this name already exists")
            level.name = data["name"]
            level.normalized_name = normalized_class_name_key(data["name"])
        level.category = target_category
        level.position = target_position
        await AcademicLevelRepository.save(db, level)
        await db.commit()
        await db.refresh(level)
        return AcademicLevelResponse.model_validate(level)

    @staticmethod
    async def purge_setup_level(db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID):
        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, academic_level_id, lock=True
        )
        if not level:
            raise NotFoundException("Academic level not found")
        counts = await AcademicLevelRepository.count_setup_dependencies(
            db, actor.tenant_id, level.id
        )
        if any(counts.values()):
            raise ConflictException(
                "This academic level is already referenced and cannot be removed.",
                payload={"dependency_counts": counts},
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
        academic_level_id: uuid.UUID,
        payload: DepartmentCreate,
    ):
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(db, actor.tenant_id, academic_level_id)
        if not level or not level.is_active or level.archived_at:
            raise NotFoundException("Active academic level not found")
        institution_type = await _tenant_institution_type(db, actor.tenant_id)
        if not category_supports_departments(institution_type, level.category):
            raise ConflictException(
                "Departments are not supported by this academic level category."
            )
        name = normalize_display_text(payload.name)
        if not name:
            raise BadRequestException("Department name is required")
        normalized = name.casefold()
        if await DepartmentRepository.get_by_normalized_name(
            db, actor.tenant_id, level.id, normalized
        ):
            raise ConflictException("Department with this name already exists for this level")
        row = Department(
            tenant_id=actor.tenant_id,
            academic_level_id=level.id,
            name=name,
            normalized_name=normalized,
            is_active=True,
        )
        await DepartmentRepository.add(db, row)
        await db.commit()
        await db.refresh(row)
        return DepartmentResponse.model_validate(row)

    @staticmethod
    async def list(db: AsyncSession, actor, academic_level_id: uuid.UUID, *, active_only=False):
        rows = await DepartmentRepository.list_for_level(
            db, actor.tenant_id, academic_level_id, active_only=active_only
        )
        return [DepartmentResponse.model_validate(row) for row in rows]


class ArmLabelService:
    @staticmethod
    async def create(db: AsyncSession, actor: TenantAdmin, payload: ArmLabelCreate):
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        label = normalize_class_arm(payload.label)
        if not label:
            raise BadRequestException("Arm label is required")
        normalized = normalized_class_arm_key(label)
        if await ArmLabelRepository.get_by_normalized_label(db, actor.tenant_id, normalized):
            raise ConflictException("Arm label with this name already exists")
        row = ArmLabel(
            tenant_id=actor.tenant_id, label=label, normalized_label=normalized, is_active=True
        )
        await ArmLabelRepository.add(db, row)
        await db.commit()
        await db.refresh(row)
        return ArmLabelResponse.model_validate(row)

    @staticmethod
    async def list(db: AsyncSession, actor, *, active_only=False, include_archived=False):
        rows = await ArmLabelRepository.list_for_tenant(
            db,
            actor.tenant_id,
            active_only=active_only,
            include_archived=include_archived and isinstance(actor, TenantAdmin),
        )
        return [ArmLabelResponse.model_validate(row) for row in rows]

    @staticmethod
    async def update(
        db: AsyncSession, actor: TenantAdmin, arm_label_id: uuid.UUID, payload: ArmLabelUpdate
    ):
        row = await ArmLabelRepository.get_by_id(db, actor.tenant_id, arm_label_id, lock=True)
        if not row:
            raise NotFoundException("Arm label not found")
        if row.archived_at:
            raise ConflictException("Archived arm labels cannot be updated")
        if payload.label is not None:
            label = normalize_class_arm(payload.label)
            normalized = normalized_class_arm_key(label)
            existing = await ArmLabelRepository.get_by_normalized_label(
                db, actor.tenant_id, normalized
            )
            if existing and existing.id != row.id:
                raise ConflictException("Arm label with this name already exists")
            row.label = label
            row.normalized_label = normalized
        if payload.is_active is not None:
            row.is_active = payload.is_active
        await ArmLabelRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ArmLabelResponse.model_validate(row)

    @staticmethod
    async def archive(db: AsyncSession, actor: TenantAdmin, arm_label_id: uuid.UUID):
        row = await ArmLabelRepository.get_by_id(db, actor.tenant_id, arm_label_id, lock=True)
        if not row:
            raise NotFoundException("Arm label not found")
        count = await ArmLabelRepository.count_class_dependencies(db, actor.tenant_id, row.id)
        if count:
            raise ConflictException(
                "Arm label is used by classes and cannot be archived.",
                payload={"dependency_counts": {"classes": count}},
            )
        row.is_active = False
        row.archived_at = datetime.now(timezone.utc)
        await ArmLabelRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ArmLabelResponse.model_validate(row)


class ClassRoomService:
    @staticmethod
    async def _validate_teacher(db, tenant_id, teacher_membership_id):
        if teacher_membership_id is None:
            return
        teacher = await TeacherMembershipRepository.get_by_id(
            db, teacher_membership_id, tenant_id=tenant_id, load_account=True
        )
        if (
            not teacher
            or teacher.status != TeacherMembershipStatus.ACTIVE
            or teacher.teacher_account.account_status != TeacherAccountStatus.ACTIVE
            or not teacher.teacher_account.is_active
        ):
            raise BadRequestException("Cannot assign an inactive teacher")

    @staticmethod
    async def _validate_structure(db, tenant_id, level_id, arm_label_id):
        level = await AcademicLevelRepository.get_by_id(db, tenant_id, level_id)
        arm = await ArmLabelRepository.get_by_id(db, tenant_id, arm_label_id)
        if not level or not level.is_active or level.archived_at:
            raise BadRequestException("Academic level must be active")
        if not arm or not arm.is_active or arm.archived_at:
            raise BadRequestException("Arm label must be active")

    @staticmethod
    async def create_classroom(db, actor: TenantAdmin, payload: ClassRoomCreate):
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        await ClassRoomService._validate_structure(
            db, actor.tenant_id, payload.academic_level_id, payload.arm_label_id
        )
        await ClassRoomService._validate_teacher(db, actor.tenant_id, payload.teacher_membership_id)
        if await ClassRoomRepository.get_by_level_arm_label(
            db, actor.tenant_id, payload.academic_level_id, payload.arm_label_id
        ):
            raise ConflictException("This class arm already exists for the level")
        row = ClassRoom(
            tenant_id=actor.tenant_id,
            academic_level_id=payload.academic_level_id,
            arm_label_id=payload.arm_label_id,
            teacher_membership_id=payload.teacher_membership_id,
            is_active=True,
        )
        await ClassRoomRepository.add(db, row)
        await db.commit()
        reloaded = await ClassRoomRepository.get_by_id(db, actor.tenant_id, row.id)
        return ClassRoomResponse.model_validate(reloaded or row)

    @staticmethod
    async def get_classroom_by_id(db, actor, class_id):
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id)
        if not row:
            raise NotFoundException("Classroom not found")
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def get_all_classrooms(db, actor, skip=0, limit=100, include_archived=False):
        if isinstance(actor, TenantAdmin):
            rows = await ClassRoomRepository.list_for_tenant(
                db,
                actor.tenant_id,
                offset=skip,
                limit=min(limit, 500),
                include_archived=include_archived,
            )
        elif isinstance(actor, Teacher):
            rows = (
                await ClassRoomRepository.list_by_teacher_membership(db, actor.tenant_id, actor.id)
            )[skip : skip + limit]
        elif isinstance(actor, Student):
            rows = (
                [await ClassRoomRepository.get_by_id(db, actor.tenant_id, actor.class_id)]
                if actor.class_id
                else []
            )
        else:
            links = await StudentParentLinkRepository.get_by_parent_id(
                db=db, tenant_id=actor.tenant_id, parent_id=actor.id
            )
            ids = list(
                {link.student.class_id for link in links if link.student and link.student.class_id}
            )
            rows = await ClassRoomRepository.list_by_ids(db, actor.tenant_id, ids)
        return [ClassRoomResponse.model_validate(row) for row in rows if row]

    @staticmethod
    async def get_active_classrooms(db, actor, skip=0, limit=100):
        return [
            row
            for row in await ClassRoomService.get_all_classrooms(db, actor, skip, limit)
            if row.is_active
        ]

    @staticmethod
    async def update_classroom(
        db, actor: TenantAdmin, class_id: uuid.UUID, payload: ClassRoomUpdate
    ):
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id)
        if not row:
            raise NotFoundException("Classroom not found")
        if row.archived_at:
            raise ConflictException("Archived classrooms cannot be updated")
        data = payload.model_dump(exclude_unset=True)
        level_id = data.get("academic_level_id", row.academic_level_id)
        arm_id = data.get("arm_label_id", row.arm_label_id)
        await ClassRoomService._validate_structure(db, actor.tenant_id, level_id, arm_id)
        if "teacher_membership_id" in data:
            await ClassRoomService._validate_teacher(
                db, actor.tenant_id, data["teacher_membership_id"]
            )
        existing = await ClassRoomRepository.get_by_level_arm_label(
            db, actor.tenant_id, level_id, arm_id
        )
        if existing and existing.id != row.id:
            raise ConflictException("This class arm already exists for the level")
        for key, value in data.items():
            setattr(row, key, value)
        await ClassRoomRepository.save(db, row)
        await db.commit()
        reloaded = await ClassRoomRepository.get_by_id(db, actor.tenant_id, row.id)
        return ClassRoomResponse.model_validate(reloaded or row)

    @staticmethod
    async def _ensure_no_live_dependencies(db, tenant_id, class_id):
        for status in (AcademicStatus.ACTIVE, AcademicStatus.SUSPENDED):
            if await ClassRoomRepository.count_assigned_students_by_status(
                db, tenant_id, class_id, status
            ):
                raise ConflictException("This class still has students assigned to it.")
        if await ClassRoomRepository.count_current_enrollments(db, tenant_id, class_id):
            raise ConflictException("This class still has current student enrollments.")
        if await ClassRoomRepository.count_active_teacher_assignments(db, tenant_id, class_id):
            raise ConflictException("This class still has active teacher assignments.")

    @staticmethod
    async def deactivate_classroom(db, actor, class_id):
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id)
        if not row:
            raise NotFoundException("Classroom not found")
        if row.is_active:
            await ClassRoomService._ensure_no_live_dependencies(db, actor.tenant_id, row.id)
            row.is_active = False
            await ClassRoomRepository.save(db, row)
            await db.commit()
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def activate_classroom(db, actor, class_id):
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id)
        if not row:
            raise NotFoundException("Classroom not found")
        if row.archived_at:
            raise ConflictException("Restore this class before activation")
        row.is_active = True
        await ClassRoomRepository.save(db, row)
        await db.commit()
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def archive_classroom(db, actor, class_id):
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id)
        if not row:
            raise NotFoundException("Classroom not found")
        if row.is_active:
            raise ConflictException("Deactivate the class before archiving")
        await ClassRoomService._ensure_no_live_dependencies(db, actor.tenant_id, row.id)
        row.archived_at = datetime.now(timezone.utc)
        row.archived_by_admin_id = actor.id
        await ClassRoomRepository.save(db, row)
        await db.commit()
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def restore_classroom(db, actor, class_id):
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id)
        if not row:
            raise NotFoundException("Classroom not found")
        row.archived_at = None
        row.archived_by_admin_id = None
        row.is_active = False
        await ClassRoomRepository.save(db, row)
        await db.commit()
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def purge_setup_classroom(db, actor, class_id):
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id)
        if not row:
            raise NotFoundException("Classroom not found")
        counts = await ClassRoomRepository.count_class_dependencies(db, actor.tenant_id, row.id)
        if any(counts.values()):
            raise ConflictException(
                "This class is already referenced and cannot be removed.",
                payload={"dependency_counts": counts},
            )
        response = ClassRoomResponse.model_validate(row)
        await ClassRoomRepository.delete_classroom(db, row)
        await db.commit()
        return response


ALLOWED_CATEGORIES = {}  # intentionally unused; category_catalog is the single source of truth
