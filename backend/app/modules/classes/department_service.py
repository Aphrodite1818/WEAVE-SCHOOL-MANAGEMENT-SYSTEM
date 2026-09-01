"""Application service for canonical departments and per-level availability."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.core.utils.normalization import normalize_display_text
from app.modules.classes.category_catalog import category_supports_departments
from app.modules.classes.department_repository import (
    AcademicLevelDepartmentRepository,
    CanonicalDepartmentRepository,
)
from app.modules.classes.models import AcademicLevelDepartment, AcademicLevelStatus, Department
from app.modules.classes.repository import AcademicLevelRepository
from app.modules.classes.schemas import (
    AcademicLevelDepartmentCreate,
    AcademicLevelDepartmentResponse,
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository


class DepartmentPoolService:
    @staticmethod
    def _admin(actor: TenantAdmin) -> None:
        if not isinstance(actor, TenantAdmin) or not actor.tenant_id:
            raise NotFoundException("Tenant administrator not found")

    @staticmethod
    def _response(row: Department) -> DepartmentResponse:
        return DepartmentResponse.model_validate(row)

    @staticmethod
    def _link_response(row: AcademicLevelDepartment) -> AcademicLevelDepartmentResponse:
        return AcademicLevelDepartmentResponse(
            id=row.id,
            tenant_id=row.tenant_id,
            academic_level_id=row.academic_level_id,
            department_id=row.department_id,
            department_name=row.department.name if row.department else None,
            is_active=row.is_active,
            archived_at=row.archived_at,
            archived_by_admin_id=row.archived_by_admin_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    async def create_department(
        db: AsyncSession, actor: TenantAdmin, payload: DepartmentCreate
    ) -> DepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        name = normalize_display_text(payload.name)
        if not name:
            raise BadRequestException("Department name is required")
        normalized = name.casefold()
        existing = await CanonicalDepartmentRepository.get_by_normalized_name(
            db, actor.tenant_id, normalized
        )
        if existing is not None:
            raise ConflictException("A department with this name already exists for this school")
        row = Department(
            tenant_id=actor.tenant_id,
            name=name,
            normalized_name=normalized,
            is_active=True,
        )
        await CanonicalDepartmentRepository.add(db, row)
        await db.commit()
        await db.refresh(row)
        return DepartmentPoolService._response(row)

    @staticmethod
    async def list_departments(
        db: AsyncSession,
        actor: TenantAdmin,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> list[DepartmentResponse]:
        DepartmentPoolService._admin(actor)
        rows = await CanonicalDepartmentRepository.list_for_tenant(
            db,
            actor.tenant_id,
            active_only=active_only,
            include_archived=include_archived,
        )
        return [DepartmentPoolService._response(row) for row in rows]

    @staticmethod
    async def update_department(
        db: AsyncSession,
        actor: TenantAdmin,
        department_id: uuid.UUID,
        payload: DepartmentUpdate,
    ) -> DepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await CanonicalDepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if row is None:
            raise NotFoundException("Department not found")
        if row.archived_at is not None:
            raise ConflictException("Archived departments cannot be edited")
        name = normalize_display_text(payload.name)
        if not name:
            raise BadRequestException("Department name is required")
        normalized = name.casefold()
        duplicate = await CanonicalDepartmentRepository.get_by_normalized_name(
            db, actor.tenant_id, normalized
        )
        if duplicate is not None and duplicate.id != row.id:
            raise ConflictException("A department with this name already exists for this school")
        row.name = name
        row.normalized_name = normalized
        await CanonicalDepartmentRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return DepartmentPoolService._response(row)

    @staticmethod
    async def deactivate_department(
        db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID
    ) -> DepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await CanonicalDepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if row is None:
            raise NotFoundException("Department not found")
        if row.archived_at is not None:
            raise ConflictException("Archived departments cannot be deactivated")
        if not row.is_active:
            return DepartmentPoolService._response(row)
        counts = await CanonicalDepartmentRepository.count_level_links(db, actor.tenant_id, row.id)
        if counts["level_links_active"]:
            raise ConflictException(
                "Disable this department for every academic level before deactivating it",
                payload={"dependency_counts": counts},
            )
        row.is_active = False
        await CanonicalDepartmentRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return DepartmentPoolService._response(row)

    @staticmethod
    async def activate_department(
        db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID
    ) -> DepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await CanonicalDepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if row is None:
            raise NotFoundException("Department not found")
        if row.archived_at is not None:
            raise ConflictException("Restore this department before activating it")
        row.is_active = True
        await CanonicalDepartmentRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return DepartmentPoolService._response(row)

    @staticmethod
    async def archive_department(
        db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID
    ) -> DepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await CanonicalDepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if row is None:
            raise NotFoundException("Department not found")
        if row.archived_at is not None:
            return DepartmentPoolService._response(row)
        if row.is_active:
            raise ConflictException("Deactivate the department before archiving it")
        counts = await CanonicalDepartmentRepository.count_level_links(db, actor.tenant_id, row.id)
        if counts["level_links_active"]:
            raise ConflictException(
                "This department is still enabled for an academic level",
                payload={"dependency_counts": counts},
            )
        row.archived_at = datetime.now(timezone.utc)
        row.archived_by_admin_id = actor.id
        row.is_active = False
        await CanonicalDepartmentRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return DepartmentPoolService._response(row)

    @staticmethod
    async def restore_department(
        db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID
    ) -> DepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await CanonicalDepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if row is None:
            raise NotFoundException("Department not found")
        if row.archived_at is None:
            raise ConflictException("Only archived departments can be restored")
        row.archived_at = None
        row.archived_by_admin_id = None
        row.is_active = False
        await CanonicalDepartmentRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return DepartmentPoolService._response(row)

    @staticmethod
    async def delete_department(
        db: AsyncSession, actor: TenantAdmin, department_id: uuid.UUID
    ) -> DepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await CanonicalDepartmentRepository.get_by_id(
            db, actor.tenant_id, department_id, lock=True
        )
        if row is None:
            raise NotFoundException("Department not found")
        counts = await CanonicalDepartmentRepository.count_level_links(db, actor.tenant_id, row.id)
        if counts["level_links_total"]:
            raise ConflictException(
                "This department has level history and cannot be permanently deleted",
                payload={"dependency_counts": counts},
            )
        response = DepartmentPoolService._response(row)
        await CanonicalDepartmentRepository.delete(db, row)
        await db.commit()
        return response

    @staticmethod
    async def _eligible_level(db: AsyncSession, tenant_id: uuid.UUID, level_id: uuid.UUID):
        level = await AcademicLevelRepository.get_by_id(db, tenant_id, level_id, lock=True)
        if level is None:
            raise NotFoundException("Academic level not found")
        if level.status != AcademicLevelStatus.ACTIVE:
            raise ConflictException(
                "Academic level must be active before departments are configured"
            )
        tenant = await TenantRepository.get_by_id(db, tenant_id)
        if tenant is None or tenant.institution_type is None:
            raise ConflictException(
                "Institution type is required before departments are configured"
            )
        if not category_supports_departments(tenant.institution_type, level.category):
            raise ConflictException("Departments are not supported by this academic level category")
        return level

    @staticmethod
    async def attach_to_level(
        db: AsyncSession,
        actor: TenantAdmin,
        academic_level_id: uuid.UUID,
        payload: AcademicLevelDepartmentCreate,
    ) -> AcademicLevelDepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        await DepartmentPoolService._eligible_level(db, actor.tenant_id, academic_level_id)
        department = await CanonicalDepartmentRepository.get_by_id(
            db, actor.tenant_id, payload.department_id, lock=True
        )
        if department is None:
            raise NotFoundException("Department not found")
        if not department.is_active or department.archived_at is not None:
            raise ConflictException(
                "Department must be globally active before it can be enabled for a level"
            )
        existing = await AcademicLevelDepartmentRepository.get_for_level_department(
            db, actor.tenant_id, academic_level_id, department.id, lock=True
        )
        if existing is not None:
            if existing.archived_at is not None:
                raise ConflictException(
                    "Restore the existing level department instead of creating another"
                )
            raise ConflictException("This department is already configured for the academic level")
        row = AcademicLevelDepartment(
            tenant_id=actor.tenant_id,
            academic_level_id=academic_level_id,
            department_id=department.id,
            is_active=True,
        )
        await AcademicLevelDepartmentRepository.add(db, row)
        await db.commit()
        row = await AcademicLevelDepartmentRepository.get_by_id(db, actor.tenant_id, row.id)
        return DepartmentPoolService._link_response(row)

    @staticmethod
    async def list_for_level(
        db: AsyncSession,
        actor: TenantAdmin,
        academic_level_id: uuid.UUID,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> list[AcademicLevelDepartmentResponse]:
        DepartmentPoolService._admin(actor)
        rows = await AcademicLevelDepartmentRepository.list_for_level(
            db,
            actor.tenant_id,
            academic_level_id,
            active_only=active_only,
            include_archived=include_archived,
        )
        return [DepartmentPoolService._link_response(row) for row in rows]

    @staticmethod
    async def _link(
        db: AsyncSession,
        actor: TenantAdmin,
        academic_level_id: uuid.UUID,
        link_id: uuid.UUID,
        *,
        lock: bool = True,
    ) -> AcademicLevelDepartment:
        row = await AcademicLevelDepartmentRepository.get_by_id(
            db, actor.tenant_id, link_id, lock=lock
        )
        if row is None or row.academic_level_id != academic_level_id:
            raise NotFoundException("Academic level department not found")
        return row

    @staticmethod
    async def deactivate_level_department(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID, link_id: uuid.UUID
    ) -> AcademicLevelDepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await DepartmentPoolService._link(db, actor, academic_level_id, link_id)
        if row.archived_at is not None:
            raise ConflictException("Archived level departments cannot be deactivated")
        if not row.is_active:
            return DepartmentPoolService._link_response(row)
        counts = await AcademicLevelDepartmentRepository.count_dependencies(
            db, actor.tenant_id, row.id
        )
        live = {k: v for k, v in counts.items() if k.endswith("_live") and v > 0}
        if live:
            raise ConflictException(
                "This level department is still in operational use",
                payload={"dependency_counts": live},
            )
        row.is_active = False
        await AcademicLevelDepartmentRepository.save(db, row)
        await db.commit()
        row = await AcademicLevelDepartmentRepository.get_by_id(db, actor.tenant_id, row.id)
        return DepartmentPoolService._link_response(row)

    @staticmethod
    async def activate_level_department(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID, link_id: uuid.UUID
    ) -> AcademicLevelDepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        await DepartmentPoolService._eligible_level(db, actor.tenant_id, academic_level_id)
        row = await DepartmentPoolService._link(db, actor, academic_level_id, link_id)
        if row.archived_at is not None:
            raise ConflictException("Restore this level department before activating it")
        if not row.department.is_active or row.department.archived_at is not None:
            raise ConflictException(
                "Activate the canonical department before enabling it for a level"
            )
        row.is_active = True
        await AcademicLevelDepartmentRepository.save(db, row)
        await db.commit()
        row = await AcademicLevelDepartmentRepository.get_by_id(db, actor.tenant_id, row.id)
        return DepartmentPoolService._link_response(row)

    @staticmethod
    async def archive_level_department(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID, link_id: uuid.UUID
    ) -> AcademicLevelDepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await DepartmentPoolService._link(db, actor, academic_level_id, link_id)
        if row.archived_at is not None:
            return DepartmentPoolService._link_response(row)
        if row.is_active:
            raise ConflictException("Deactivate this level department before archiving it")
        counts = await AcademicLevelDepartmentRepository.count_dependencies(
            db, actor.tenant_id, row.id
        )
        live = {k: v for k, v in counts.items() if k.endswith("_live") and v > 0}
        if live:
            raise ConflictException(
                "This level department is still in operational use",
                payload={"dependency_counts": live},
            )
        row.archived_at = datetime.now(timezone.utc)
        row.archived_by_admin_id = actor.id
        await AcademicLevelDepartmentRepository.save(db, row)
        await db.commit()
        row = await AcademicLevelDepartmentRepository.get_by_id(db, actor.tenant_id, row.id)
        return DepartmentPoolService._link_response(row)

    @staticmethod
    async def restore_level_department(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID, link_id: uuid.UUID
    ) -> AcademicLevelDepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await DepartmentPoolService._link(db, actor, academic_level_id, link_id)
        if row.archived_at is None:
            raise ConflictException("Only archived level departments can be restored")
        if row.department.archived_at is not None:
            raise ConflictException("Restore the canonical department first")
        row.archived_at = None
        row.archived_by_admin_id = None
        row.is_active = False
        await AcademicLevelDepartmentRepository.save(db, row)
        await db.commit()
        row = await AcademicLevelDepartmentRepository.get_by_id(db, actor.tenant_id, row.id)
        return DepartmentPoolService._link_response(row)

    @staticmethod
    async def delete_level_department(
        db: AsyncSession, actor: TenantAdmin, academic_level_id: uuid.UUID, link_id: uuid.UUID
    ) -> AcademicLevelDepartmentResponse:
        DepartmentPoolService._admin(actor)
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        row = await DepartmentPoolService._link(db, actor, academic_level_id, link_id)
        counts = await AcademicLevelDepartmentRepository.count_dependencies(
            db, actor.tenant_id, row.id
        )
        if any(counts.values()):
            raise ConflictException(
                "This level department has academic history and cannot be permanently deleted",
                payload={"dependency_counts": counts},
            )
        response = DepartmentPoolService._link_response(row)
        await AcademicLevelDepartmentRepository.delete(db, row)
        await db.commit()
        return response
