"""Focused tenant-admin student contracts omitted from the core service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.students.models import AcademicStatus
from app.modules.students.repository import StudentRepository
from app.modules.students.schemas import (
    StudentAdminProfileUpdate,
    StudentDetailResponse,
)
from app.modules.students.service import StudentService
from app.modules.tenant_admins.models import TenantAdmin


class StudentAdminContractService:
    """Admin read/update operations with explicit archival and PATCH semantics."""

    @staticmethod
    async def _materialize_due_returns(db: AsyncSession, tenant_id: UUID) -> None:
        """Apply date-effective formal returns without a scheduler."""

        from app.modules.students.lifecycle_service import StudentLifecycleService

        await StudentLifecycleService.activate_due_returns_for_tenant(
            db,
            tenant_id=tenant_id,
        )

    @staticmethod
    async def _with_lifecycle_capabilities(
        db: AsyncSession,
        student: StudentDetailResponse,
    ) -> StudentDetailResponse:
        from app.modules.students.lifecycle_service import StudentLifecycleService

        capabilities = await StudentLifecycleService.capabilities(
            db,
            tenant_id=student.tenant_id,
            student_id=student.id,
        )
        return student.model_copy(update={"lifecycle_capabilities": capabilities})

    @staticmethod
    async def list_students(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        class_id: UUID | None = None,
        academic_level_id: UUID | None = None,
        unassigned_class: bool = False,
        status: AcademicStatus | None = None,
        include_archived: bool = False,
    ) -> tuple[list[StudentDetailResponse], int]:
        await StudentAdminContractService._materialize_due_returns(db, actor.tenant_id)
        students, total = await StudentRepository.list_for_tenant(
            db,
            actor.tenant_id,
            search=search,
            class_id=class_id,
            academic_level_id=academic_level_id,
            unassigned_class=unassigned_class,
            status=status,
            include_archived=include_archived,
            offset=skip,
            limit=min(limit, 100),
        )
        responses = [
            await StudentService._build_detail_response(db, student) for student in students
        ]
        return [
            await StudentAdminContractService._with_lifecycle_capabilities(db, student)
            for student in responses
        ], total

    @staticmethod
    async def get_student(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
    ) -> StudentDetailResponse:
        await StudentAdminContractService._materialize_due_returns(db, actor.tenant_id)
        student = await StudentService.get_student_profile(db, actor, student_id)
        return await StudentAdminContractService._with_lifecycle_capabilities(db, student)

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        payload: StudentAdminProfileUpdate,
    ) -> StudentDetailResponse:
        student = await StudentRepository.get_by_id(
            db,
            actor.tenant_id,
            student_id,
            lock=True,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")

        update_data = payload.model_dump(exclude_unset=True)
        for required_field in ("first_name", "last_name", "date_of_birth"):
            if required_field in update_data and update_data[required_field] is None:
                raise BadRequestException(
                    f"{required_field} cannot be cleared from an admitted student."
                )

        for field, value in update_data.items():
            setattr(student, field, value)

        student.profile_status = StudentService._resolve_profile_status(student)
        await StudentRepository.save(db, student)
        await db.commit()
        await db.refresh(student)
        return await StudentService._build_detail_response(db, student)
