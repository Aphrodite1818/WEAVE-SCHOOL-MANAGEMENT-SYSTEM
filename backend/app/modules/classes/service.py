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
    AcademicLevelStatus,
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
    DepartmentUpdate,
)
from app.modules.parents.models import Parent
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.students.models import Student
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
    async def _validate_specialization_rule(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        category: AcademicCategory,
        specialization_required_from_term_position: int | None,
    ) -> None:
        if specialization_required_from_term_position is None:
            return

        institution_type = await _tenant_institution_type(db, tenant_id)

        if not category_supports_departments(institution_type, category):
            raise BadRequestException(
                "Department specialization cannot be required for this academic level category"
            )

    @staticmethod
    def _has_any_usage(dependencies: dict[str, int]) -> bool:
        historical_keys = (
            "classes_total",
            "departments_total",
            "curriculum_subjects_total",
            "enrollments_total",
        )
        return any(dependencies.get(key, 0) > 0 for key in historical_keys)

    @staticmethod
    def _has_live_dependencies(dependencies: dict[str, int]) -> bool:
        live_keys = (
            "classes_active",
            "departments_active",
            "curriculum_subjects_active",
            "enrollments_current",
        )
        return any(dependencies.get(key, 0) > 0 for key in live_keys)

    @staticmethod
    def _can_hard_delete(dependencies: dict[str, int]) -> bool:
        return not AcademicLevelService._has_any_usage(dependencies)

    @staticmethod
    def _can_archive(dependencies: dict[str, int]) -> bool:
        return not AcademicLevelService._has_live_dependencies(dependencies)

    @staticmethod
    def _live_dependency_counts(dependencies: dict[str, int]) -> dict[str, int]:
        return {
            key: value
            for key, value in dependencies.items()
            if key
            in {
                "classes_active",
                "departments_active",
                "curriculum_subjects_active",
                "enrollments_current",
            }
            and value > 0
        }

    @staticmethod
    async def _validate_publication_contract(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        level: AcademicLevel,
    ) -> None:
        await AcademicLevelService._validate_category(db, tenant_id, level.category)
        await AcademicLevelService._validate_specialization_rule(
            db,
            tenant_id,
            category=level.category,
            specialization_required_from_term_position=(
                level.specialization_required_from_term_position
            ),
        )
        owner = await AcademicLevelRepository.get_by_category_position(
            db,
            tenant_id,
            level.category,
            level.position,
            exclude_id=level.id,
        )
        if owner:
            raise ConflictException("Another academic level already uses this category position")

    @staticmethod
    def _ensure_active_level(level: AcademicLevel | None, *, missing_message: str) -> AcademicLevel:
        if level is None or level.status != AcademicLevelStatus.ACTIVE:
            raise NotFoundException(missing_message)
        return level

    @staticmethod
    async def create(
        db: AsyncSession, actor: TenantAdmin, payload: AcademicLevelCreate
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        await AcademicLevelService._validate_category(db, actor.tenant_id, payload.category)
        await AcademicLevelService._validate_specialization_rule(
            db,
            actor.tenant_id,
            category=payload.category,
            specialization_required_from_term_position=(
                payload.specialization_required_from_term_position
            ),
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
            status=AcademicLevelStatus.DRAFT,
            specialization_required_from_term_position=payload.specialization_required_from_term_position,
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
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, academic_level_id, lock=True
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.status == AcademicLevelStatus.ARCHIVED:
            raise ConflictException("Archived academic levels cannot be updated")
        data = payload.model_dump(exclude_unset=True)
        structural_fields = {
            "category",
            "position",
            "specialization_required_from_term_position",
        }
        if level.status != AcademicLevelStatus.DRAFT and structural_fields.intersection(data):
            raise ConflictException(
                "Academic level structure is locked after activation. Only the name can be edited."
            )
        if "category" in data:
            await AcademicLevelService._validate_category(db, actor.tenant_id, data["category"])
        target_category = data.get("category", level.category)
        target_position = data.get("position", level.position)
        target_specialization_position = data.get(
            "specialization_required_from_term_position",
            level.specialization_required_from_term_position,
        )

        await AcademicLevelService._validate_specialization_rule(
            db,
            actor.tenant_id,
            category=target_category,
            specialization_required_from_term_position=target_specialization_position,
        )
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
        level.specialization_required_from_term_position = target_specialization_position
        await AcademicLevelRepository.save(db, level)
        await db.commit()
        await db.refresh(level)
        return AcademicLevelResponse.model_validate(level)

    @staticmethod
    async def activate(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, academic_level_id, lock=True
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.status == AcademicLevelStatus.ARCHIVED:
            raise ConflictException("Restore this academic level before activation")
        if level.status == AcademicLevelStatus.ACTIVE:
            return AcademicLevelResponse.model_validate(level)
        if level.status not in {AcademicLevelStatus.DRAFT, AcademicLevelStatus.INACTIVE}:
            raise ConflictException("Academic level cannot be activated from its current status")
        if level.status == AcademicLevelStatus.DRAFT:
            await AcademicLevelService._validate_publication_contract(db, actor.tenant_id, level)
        level.status = AcademicLevelStatus.ACTIVE
        await AcademicLevelRepository.save(db, level)
        await db.commit()
        await db.refresh(level)
        return AcademicLevelResponse.model_validate(level)

    @staticmethod
    async def deactivate(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, academic_level_id, lock=True
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.status != AcademicLevelStatus.ACTIVE:
            raise ConflictException("Only active academic levels can be deactivated")
        counts = await AcademicLevelRepository.count_setup_dependencies(
            db, actor.tenant_id, level.id
        )
        live_counts = AcademicLevelService._live_dependency_counts(counts)
        if live_counts:
            raise ConflictException(
                "This academic level still has live dependencies and cannot be deactivated.",
                payload={"dependency_counts": live_counts},
            )
        level.status = AcademicLevelStatus.INACTIVE
        await AcademicLevelRepository.save(db, level)
        await db.commit()
        await db.refresh(level)
        return AcademicLevelResponse.model_validate(level)

    @staticmethod
    async def archive(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, academic_level_id, lock=True
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.status == AcademicLevelStatus.DRAFT:
            raise ConflictException("Delete draft academic levels instead of archiving them")
        if level.status == AcademicLevelStatus.ACTIVE:
            raise ConflictException("Deactivate the academic level before archiving")
        if level.status == AcademicLevelStatus.ARCHIVED:
            return AcademicLevelResponse.model_validate(level)
        counts = await AcademicLevelRepository.count_setup_dependencies(
            db, actor.tenant_id, level.id
        )
        live_counts = AcademicLevelService._live_dependency_counts(counts)
        if live_counts:
            raise ConflictException(
                "This academic level still has live dependencies and cannot be archived.",
                payload={"dependency_counts": live_counts},
            )
        level.status = AcademicLevelStatus.ARCHIVED
        level.archived_at = datetime.now(timezone.utc)
        level.archived_by_admin_id = actor.id
        await AcademicLevelRepository.save(db, level)
        await db.commit()
        await db.refresh(level)
        return AcademicLevelResponse.model_validate(level)

    @staticmethod
    async def restore(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, academic_level_id, lock=True
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.status != AcademicLevelStatus.ARCHIVED:
            raise ConflictException("Only archived academic levels can be restored")
        level.status = AcademicLevelStatus.INACTIVE
        level.archived_at = None
        level.archived_by_admin_id = None
        await AcademicLevelRepository.save(db, level)
        await db.commit()
        await db.refresh(level)
        return AcademicLevelResponse.model_validate(level)

    @staticmethod
    async def delete_if_unused(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID
    ) -> AcademicLevelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, academic_level_id, lock=True
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.status != AcademicLevelStatus.DRAFT:
            raise ConflictException("Only draft academic levels can be deleted")
        counts = await AcademicLevelRepository.count_setup_dependencies(
            db, actor.tenant_id, level.id
        )
        if not AcademicLevelService._can_hard_delete(counts):
            raise ConflictException(
                "This academic level is already referenced and cannot be removed.",
                payload={"dependency_counts": counts},
            )
        response = AcademicLevelResponse.model_validate(level)
        await AcademicLevelRepository.delete(db, level)
        await db.commit()
        return response

    purge_setup_level = delete_if_unused


class DepartmentService:
    @staticmethod
    async def create(
        db: AsyncSession,
        actor: TenantAdmin,
        academic_level_id: uuid.UUID,
        payload: DepartmentCreate,
    ) -> DepartmentResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        level = await AcademicLevelRepository.get_by_id(db, actor.tenant_id, academic_level_id)
        level = AcademicLevelService._ensure_active_level(
            level, missing_message="Active academic level not found"
        )
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
    async def list(
        db: AsyncSession,
        actor,
        academic_level_id: uuid.UUID,
        *,
        active_only=False,
        include_archived: bool = False,
    ) -> list[DepartmentResponse]:
        if not actor.tenant_id:
            raise ForbiddenException("Actor is not attached to a tenant")

        is_admin = isinstance(actor, TenantAdmin)
        effective_active_only = active_only if is_admin else True

        rows = await DepartmentRepository.list_for_level(
            db,
            actor.tenant_id,
            academic_level_id,
            active_only=effective_active_only,
            include_archived=(include_archived and is_admin),
        )
        return [DepartmentResponse.model_validate(row) for row in rows]

    @staticmethod
    def _live_dependency_counts(dependencies: dict[str, int]) -> dict[str, int]:
        live_keys = ("class_assignments_live", "offerings_live")
        return {key: dependencies.get(key, 0) for key in live_keys if dependencies.get(key, 0) > 0}

    @staticmethod
    def _has_any_usage(dependencies: dict[str, int]) -> bool:
        return (
            dependencies.get("class_assignments_total", 0) > 0
            or dependencies.get("offerings_total", 0) > 0
        )

    @staticmethod
    async def deactivate(
        db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID
    ) -> DepartmentResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        department = await DepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if department is None:
            raise NotFoundException("Department not found")
        if department.archived_at is not None:
            raise ConflictException("Archived departments cannot be deactivated")
        if not department.is_active:
            return DepartmentResponse.model_validate(department)

        dependencies = await DepartmentRepository.count_dependencies(
            db, actor.tenant_id, department.id
        )
        live_dependencies = DepartmentService._live_dependency_counts(dependencies)
        if live_dependencies:
            raise ConflictException(
                "This department still has live academic dependencies and cannot be deactivated",
                payload={"dependency_counts": live_dependencies},
            )

        department.is_active = False
        await DepartmentRepository.save(db, department)
        await db.commit()
        await db.refresh(department)
        return DepartmentResponse.model_validate(department)

    @staticmethod
    async def activate(
        db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID
    ) -> DepartmentResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        department = await DepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if department is None:
            raise NotFoundException("Department not found")
        if department.archived_at is not None:
            raise ConflictException("Restore this department before activating it")
        if department.is_active:
            return DepartmentResponse.model_validate(department)

        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, department.academic_level_id
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.status != AcademicLevelStatus.ACTIVE:
            raise ConflictException(
                "The academic level must be active before this department can be activated"
            )

        institution_type = await _tenant_institution_type(db, actor.tenant_id)
        if not category_supports_departments(institution_type, level.category):
            raise ConflictException("Departments are not supported by this academic level category")

        department.is_active = True
        await DepartmentRepository.save(db, department)
        await db.commit()
        await db.refresh(department)
        return DepartmentResponse.model_validate(department)

    @staticmethod
    async def restore(db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID):
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        department = await DepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if department is None:
            raise NotFoundException("Department not found")
        if department.archived_at is None:
            raise ConflictException("Only archived departments can be restored")

        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, department.academic_level_id
        )
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.status == AcademicLevelStatus.ARCHIVED:
            raise ConflictException("Restore the academic level before restoring this department")

        department.archived_at = None
        department.archived_by_admin_id = None
        department.is_active = False
        await DepartmentRepository.save(db, department)
        await db.commit()
        await db.refresh(department)
        return DepartmentResponse.model_validate(department)

    @staticmethod
    async def archive(
        db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID
    ) -> DepartmentResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        department = await DepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if department is None:
            raise NotFoundException("Department not found")
        if department.archived_at is not None:
            return DepartmentResponse.model_validate(department)
        if department.is_active:
            raise ConflictException("Deactivate the department before archiving it")

        dependencies = await DepartmentRepository.count_dependencies(
            db, actor.tenant_id, department.id
        )
        live_dependencies = DepartmentService._live_dependency_counts(dependencies)
        if live_dependencies:
            raise ConflictException(
                "This department still has live academic dependencies and cannot be archived",
                payload={"dependency_counts": live_dependencies},
            )

        department.is_active = False
        department.archived_at = datetime.now(timezone.utc)
        department.archived_by_admin_id = actor.id
        await DepartmentRepository.save(db, department)
        await db.commit()
        await db.refresh(department)
        return DepartmentResponse.model_validate(department)

    @staticmethod
    async def update(
        db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID, payload: DepartmentUpdate
    ) -> DepartmentResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        department = await DepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if department is None:
            raise NotFoundException("Department not found")
        if department.archived_at is not None:
            raise ConflictException("Archived departments cannot be updated")

        data = payload.model_dump(exclude_unset=True)
        if "name" not in data:
            return DepartmentResponse.model_validate(department)

        name = normalize_display_text(data["name"])
        if not name:
            raise BadRequestException("Department name is required")
        normalized = name.casefold()

        if normalized == department.normalized_name:
            department.name = name
            await DepartmentRepository.save(db, department)
            await db.commit()
            await db.refresh(department)
            return DepartmentResponse.model_validate(department)

        dependencies = await DepartmentRepository.count_dependencies(
            db, actor.tenant_id, department.id
        )
        if DepartmentService._has_any_usage(dependencies):
            raise ConflictException(
                "This department has already been used and can no longer be renamed.",
                payload={"dependency_counts": dependencies},
            )

        existing = await DepartmentRepository.get_by_normalized_name(
            db,
            actor.tenant_id,
            department.academic_level_id,
            normalized,
        )
        if existing is not None and existing.id != department.id:
            raise ConflictException("Department with this name already exists for this level.")

        department.name = name
        department.normalized_name = normalized
        await DepartmentRepository.save(db, department)
        await db.commit()
        await db.refresh(department)
        return DepartmentResponse.model_validate(department)

    @staticmethod
    async def hard_delete(
        db: AsyncSession,
        actor: TenantAdmin,
        department_id: uuid.UUID,
    ) -> DepartmentResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        department = await DepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if department is None:
            raise NotFoundException("Department not found")

        dependencies = await DepartmentRepository.count_dependencies(
            db, actor.tenant_id, department.id
        )
        if DepartmentService._has_any_usage(dependencies):
            raise ConflictException(
                "This department has already been used and cannot be permanently deleted.",
                payload={"dependency_counts": dependencies},
            )

        response = DepartmentResponse.model_validate(department)
        await DepartmentRepository.delete(db, department)
        await db.commit()
        return response


class ArmLabelService:
    @staticmethod
    def _has_any_usage(dependencies: dict[str, int]) -> bool:
        return dependencies.get("classes_total", 0) > 0

    @staticmethod
    def _live_dependency_counts(dependencies: dict[str, int]) -> dict[str, int]:
        classes_live = dependencies.get("classes_live", 0)
        return {"classes_live": classes_live} if classes_live > 0 else {}

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
            tenant_id=actor.tenant_id,
            label=label,
            normalized_label=normalized,
            is_active=True,
        )
        await ArmLabelRepository.add(db, row)
        await db.commit()
        await db.refresh(row)
        return ArmLabelResponse.model_validate(row)

    @staticmethod
    async def list(db: AsyncSession, actor, *, active_only=False, include_archived=False):
        if not actor.tenant_id:
            raise ForbiddenException("Actor is not attached to a tenant")

        is_admin = isinstance(actor, TenantAdmin)
        effective_active_only = active_only if is_admin else True
        rows = await ArmLabelRepository.list_for_tenant(
            db,
            actor.tenant_id,
            active_only=effective_active_only,
            include_archived=include_archived and is_admin,
        )
        return [ArmLabelResponse.model_validate(row) for row in rows]

    @staticmethod
    async def update(
        db: AsyncSession, actor: TenantAdmin, arm_label_id: uuid.UUID, payload: ArmLabelUpdate
    ) -> ArmLabelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ArmLabelRepository.get_by_id(db, actor.tenant_id, arm_label_id, lock=True)
        if row is None:
            raise NotFoundException("Arm label not found")
        if row.archived_at is not None:
            raise ConflictException("Archived arm labels cannot be updated")

        label = normalize_class_arm(payload.label)
        if not label:
            raise BadRequestException("Arm label is required")
        normalized = normalized_class_arm_key(label)

        if normalized == row.normalized_label:
            row.label = label
            await ArmLabelRepository.save(db, row)
            await db.commit()
            await db.refresh(row)
            return ArmLabelResponse.model_validate(row)

        dependencies = await ArmLabelRepository.count_dependencies(
            db, actor.tenant_id, row.id
        )
        if ArmLabelService._has_any_usage(dependencies):
            raise ConflictException(
                "This arm label has already been used and can no longer be renamed.",
                payload={"dependency_counts": dependencies},
            )

        existing = await ArmLabelRepository.get_by_normalized_label(
            db, actor.tenant_id, normalized
        )
        if existing is not None and existing.id != row.id:
            raise ConflictException("Arm label with this name already exists")

        row.label = label
        row.normalized_label = normalized
        await ArmLabelRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ArmLabelResponse.model_validate(row)

    @staticmethod
    async def deactivate(
        db: AsyncSession, actor: TenantAdmin, arm_label_id: uuid.UUID
    ) -> ArmLabelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ArmLabelRepository.get_by_id(db, actor.tenant_id, arm_label_id, lock=True)
        if row is None:
            raise NotFoundException("Arm label not found")
        if row.archived_at is not None:
            raise ConflictException("Archived arm labels cannot be deactivated")
        if not row.is_active:
            return ArmLabelResponse.model_validate(row)

        dependencies = await ArmLabelRepository.count_dependencies(
            db, actor.tenant_id, row.id
        )
        live_dependencies = ArmLabelService._live_dependency_counts(dependencies)
        if live_dependencies:
            raise ConflictException(
                "This arm label still has active classrooms and cannot be deactivated.",
                payload={"dependency_counts": live_dependencies},
            )

        row.is_active = False
        await ArmLabelRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ArmLabelResponse.model_validate(row)

    @staticmethod
    async def activate(
        db: AsyncSession, actor: TenantAdmin, arm_label_id: uuid.UUID
    ) -> ArmLabelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ArmLabelRepository.get_by_id(db, actor.tenant_id, arm_label_id, lock=True)
        if row is None:
            raise NotFoundException("Arm label not found")
        if row.archived_at is not None:
            raise ConflictException("Restore this arm label before activating it")
        if row.is_active:
            return ArmLabelResponse.model_validate(row)

        row.is_active = True
        await ArmLabelRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ArmLabelResponse.model_validate(row)

    @staticmethod
    async def archive(
        db: AsyncSession, actor: TenantAdmin, arm_label_id: uuid.UUID
    ) -> ArmLabelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ArmLabelRepository.get_by_id(db, actor.tenant_id, arm_label_id, lock=True)
        if row is None:
            raise NotFoundException("Arm label not found")
        if row.archived_at is not None:
            return ArmLabelResponse.model_validate(row)
        if row.is_active:
            raise ConflictException("Deactivate the arm label before archiving it")

        dependencies = await ArmLabelRepository.count_dependencies(
            db, actor.tenant_id, row.id
        )
        live_dependencies = ArmLabelService._live_dependency_counts(dependencies)
        if live_dependencies:
            raise ConflictException(
                "This arm label still has active classrooms and cannot be archived.",
                payload={"dependency_counts": live_dependencies},
            )

        row.is_active = False
        row.archived_at = datetime.now(timezone.utc)
        row.archived_by_admin_id = actor.id
        await ArmLabelRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ArmLabelResponse.model_validate(row)

    @staticmethod
    async def restore(
        db: AsyncSession, actor: TenantAdmin, arm_label_id: uuid.UUID
    ) -> ArmLabelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ArmLabelRepository.get_by_id(db, actor.tenant_id, arm_label_id, lock=True)
        if row is None:
            raise NotFoundException("Arm label not found")
        if row.archived_at is None:
            raise ConflictException("Only archived arm labels can be restored")

        row.archived_at = None
        row.archived_by_admin_id = None
        row.is_active = False
        await ArmLabelRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ArmLabelResponse.model_validate(row)

    @staticmethod
    async def hard_delete(
        db: AsyncSession, actor: TenantAdmin, arm_label_id: uuid.UUID
    ) -> ArmLabelResponse:
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ArmLabelRepository.get_by_id(db, actor.tenant_id, arm_label_id, lock=True)
        if row is None:
            raise NotFoundException("Arm label not found")

        dependencies = await ArmLabelRepository.count_dependencies(
            db, actor.tenant_id, row.id
        )
        if ArmLabelService._has_any_usage(dependencies):
            raise ConflictException(
                "This arm label has already been used and cannot be permanently deleted.",
                payload={"dependency_counts": dependencies},
            )

        response = ArmLabelResponse.model_validate(row)
        await ArmLabelRepository.delete(db, row)
        await db.commit()
        return response


class ClassRoomService:
    LIVE_DEPENDENCY_KEYS = (
        "students_assigned_live",
        "enrollments_current",
        "teacher_assignments_active",
        "department_assignments_live",
        "results_live",
        "attendance_sheets_live",
        "report_cards_live",
        "progression_items_live",
    )

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
        if not level or level.status != AcademicLevelStatus.ACTIVE:
            raise BadRequestException("Academic level must be active")
        if not arm or not arm.is_active or arm.archived_at:
            raise BadRequestException("Arm label must be active")

    @staticmethod
    def _has_any_usage(dependencies: dict[str, int]) -> bool:
        return any(value > 0 for key, value in dependencies.items() if key.endswith("_total"))

    @staticmethod
    def _live_dependency_counts(dependencies: dict[str, int]) -> dict[str, int]:
        return {
            key: dependencies.get(key, 0)
            for key in ClassRoomService.LIVE_DEPENDENCY_KEYS
            if dependencies.get(key, 0) > 0
        }

    @staticmethod
    async def _ensure_no_live_dependencies(db, tenant_id, class_id):
        dependencies = await ClassRoomRepository.count_class_dependencies(db, tenant_id, class_id)
        live_dependencies = ClassRoomService._live_dependency_counts(dependencies)
        if live_dependencies:
            raise ConflictException(
                "This class still has live academic dependencies.",
                payload={"dependency_counts": live_dependencies},
            )

    @staticmethod
    async def create_classroom(db, actor: TenantAdmin, payload: ClassRoomCreate):
        AcademicLevelService._ensure_admin(actor)
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
        if not actor.tenant_id:
            raise ForbiddenException("Actor is not attached to a tenant")
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id)
        if not row:
            raise NotFoundException("Classroom not found")
        if not isinstance(actor, TenantAdmin) and (not row.is_active or row.archived_at is not None):
            raise NotFoundException("Classroom not found")
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def get_all_classrooms(db, actor, skip=0, limit=100, include_archived=False):
        if not actor.tenant_id:
            raise ForbiddenException("Actor is not attached to a tenant")

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
            rows = await ClassRoomRepository.list_by_ids(
                db,
                actor.tenant_id,
                ids,
                active_only=True,
            )

        if not isinstance(actor, TenantAdmin):
            rows = [row for row in rows if row and row.is_active and row.archived_at is None]

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
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id, lock=True)
        if not row:
            raise NotFoundException("Classroom not found")
        if row.archived_at:
            raise ConflictException("Archived classrooms cannot be updated")

        data = payload.model_dump(exclude_unset=True)
        level_id = data.get("academic_level_id", row.academic_level_id)
        arm_id = data.get("arm_label_id", row.arm_label_id)
        structural_change = (
            ("academic_level_id" in data and level_id != row.academic_level_id)
            or ("arm_label_id" in data and arm_id != row.arm_label_id)
        )

        if structural_change:
            dependencies = await ClassRoomRepository.count_class_dependencies(
                db, actor.tenant_id, row.id
            )
            if ClassRoomService._has_any_usage(dependencies):
                raise ConflictException(
                    "Classroom level and arm are locked after the class is first used.",
                    payload={"dependency_counts": dependencies},
                )
            await ClassRoomService._validate_structure(db, actor.tenant_id, level_id, arm_id)
            existing = await ClassRoomRepository.get_by_level_arm_label(
                db, actor.tenant_id, level_id, arm_id
            )
            if existing and existing.id != row.id:
                raise ConflictException("This class arm already exists for the level")

        if "teacher_membership_id" in data:
            await ClassRoomService._validate_teacher(
                db, actor.tenant_id, data["teacher_membership_id"]
            )

        for key, value in data.items():
            setattr(row, key, value)
        await ClassRoomRepository.save(db, row)
        await db.commit()
        reloaded = await ClassRoomRepository.get_by_id(db, actor.tenant_id, row.id)
        return ClassRoomResponse.model_validate(reloaded or row)

    @staticmethod
    async def deactivate_classroom(db, actor: TenantAdmin, class_id):
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id, lock=True)
        if not row:
            raise NotFoundException("Classroom not found")
        if row.archived_at is not None:
            raise ConflictException("Archived classrooms cannot be deactivated")
        if not row.is_active:
            return ClassRoomResponse.model_validate(row)

        await ClassRoomService._ensure_no_live_dependencies(db, actor.tenant_id, row.id)
        row.is_active = False
        await ClassRoomRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def activate_classroom(db, actor: TenantAdmin, class_id):
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id, lock=True)
        if not row:
            raise NotFoundException("Classroom not found")
        if row.archived_at:
            raise ConflictException("Restore this class before activation")
        if row.is_active:
            return ClassRoomResponse.model_validate(row)

        await ClassRoomService._validate_structure(
            db, actor.tenant_id, row.academic_level_id, row.arm_label_id
        )
        row.is_active = True
        await ClassRoomRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def archive_classroom(db, actor: TenantAdmin, class_id):
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id, lock=True)
        if not row:
            raise NotFoundException("Classroom not found")
        if row.archived_at is not None:
            return ClassRoomResponse.model_validate(row)
        if row.is_active:
            raise ConflictException("Deactivate the class before archiving")

        await ClassRoomService._ensure_no_live_dependencies(db, actor.tenant_id, row.id)
        row.is_active = False
        row.archived_at = datetime.now(timezone.utc)
        row.archived_by_admin_id = actor.id
        await ClassRoomRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def restore_classroom(db, actor: TenantAdmin, class_id):
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id, lock=True)
        if not row:
            raise NotFoundException("Classroom not found")
        if row.archived_at is None:
            raise ConflictException("Only archived classrooms can be restored")

        level = await AcademicLevelRepository.get_by_id(db, actor.tenant_id, row.academic_level_id)
        arm = await ArmLabelRepository.get_by_id(db, actor.tenant_id, row.arm_label_id)
        if level is None:
            raise NotFoundException("Academic level not found")
        if arm is None:
            raise NotFoundException("Arm label not found")
        if level.status == AcademicLevelStatus.ARCHIVED:
            raise ConflictException("Restore the academic level before restoring this class")
        if arm.archived_at is not None:
            raise ConflictException("Restore the arm label before restoring this class")

        row.archived_at = None
        row.archived_by_admin_id = None
        row.is_active = False
        await ClassRoomRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return ClassRoomResponse.model_validate(row)

    @staticmethod
    async def purge_setup_classroom(db, actor: TenantAdmin, class_id):
        AcademicLevelService._ensure_admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await ClassRoomRepository.get_by_id(db, actor.tenant_id, class_id, lock=True)
        if not row:
            raise NotFoundException("Classroom not found")

        counts = await ClassRoomRepository.count_class_dependencies(db, actor.tenant_id, row.id)
        if ClassRoomService._has_any_usage(counts):
            raise ConflictException(
                "This class is already referenced and cannot be removed.",
                payload={"dependency_counts": counts},
            )

        response = ClassRoomResponse.model_validate(row)
        await ClassRoomRepository.delete_classroom(db, row)
        await db.commit()
        return response


ALLOWED_CATEGORIES = {}  # intentionally unused; category_catalog is the single source of truth
