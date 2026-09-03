"""Repositories for canonical departments and per-level availability."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.classes.models import AcademicLevelDepartment, Department
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    CurriculumSubject,
    CurriculumSubjectDepartment,
)
from app.modules.student_academics.models import AcademicTerm, AcademicTermStatus


class CanonicalDepartmentRepository:
    @staticmethod
    async def add(db: AsyncSession, row: Department) -> Department:
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def save(db: AsyncSession, row: Department) -> Department:
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def delete(db: AsyncSession, row: Department) -> None:
        await db.delete(row)

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Department | None:
        query = select(Department).where(
            Department.tenant_id == tenant_id,
            Department.id == department_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_by_normalized_name(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        normalized_name: str,
    ) -> Department | None:
        return (
            await db.execute(
                select(Department).where(
                    Department.tenant_id == tenant_id,
                    Department.normalized_name == normalized_name,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> list[Department]:
        query = select(Department).where(Department.tenant_id == tenant_id)
        if active_only:
            query = query.where(
                Department.is_active.is_(True),
                Department.archived_at.is_(None),
            )
        elif not include_archived:
            query = query.where(Department.archived_at.is_(None))
        return list((await db.execute(query.order_by(Department.name))).scalars())

    @staticmethod
    async def count_level_links(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> dict[str, int]:
        row = (
            await db.execute(
                select(
                    func.count(AcademicLevelDepartment.id).label("total"),
                    func.count(AcademicLevelDepartment.id)
                    .filter(
                        AcademicLevelDepartment.is_active.is_(True),
                        AcademicLevelDepartment.archived_at.is_(None),
                    )
                    .label("active"),
                ).where(
                    AcademicLevelDepartment.tenant_id == tenant_id,
                    AcademicLevelDepartment.department_id == department_id,
                )
            )
        ).one()
        return {"level_links_total": int(row.total), "level_links_active": int(row.active)}


class AcademicLevelDepartmentRepository:
    LOAD = (
        joinedload(AcademicLevelDepartment.department),
        joinedload(AcademicLevelDepartment.academic_level),
    )

    @staticmethod
    async def add(db: AsyncSession, row: AcademicLevelDepartment) -> AcademicLevelDepartment:
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def save(db: AsyncSession, row: AcademicLevelDepartment) -> AcademicLevelDepartment:
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def delete(db: AsyncSession, row: AcademicLevelDepartment) -> None:
        await db.delete(row)

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        link_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> AcademicLevelDepartment | None:
        query = (
            select(AcademicLevelDepartment)
            .options(*AcademicLevelDepartmentRepository.LOAD)
            .where(
                AcademicLevelDepartment.tenant_id == tenant_id,
                AcademicLevelDepartment.id == link_id,
            )
        )
        if lock:
            query = query.with_for_update(of=AcademicLevelDepartment)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_for_level_department(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        department_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> AcademicLevelDepartment | None:
        query = (
            select(AcademicLevelDepartment)
            .options(*AcademicLevelDepartmentRepository.LOAD)
            .where(
                AcademicLevelDepartment.tenant_id == tenant_id,
                AcademicLevelDepartment.academic_level_id == academic_level_id,
                AcademicLevelDepartment.department_id == department_id,
            )
        )
        if lock:
            query = query.with_for_update(of=AcademicLevelDepartment)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_for_level(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> list[AcademicLevelDepartment]:
        query = (
            select(AcademicLevelDepartment)
            .options(*AcademicLevelDepartmentRepository.LOAD)
            .join(Department, Department.id == AcademicLevelDepartment.department_id)
            .where(
                AcademicLevelDepartment.tenant_id == tenant_id,
                AcademicLevelDepartment.academic_level_id == academic_level_id,
                Department.tenant_id == tenant_id,
            )
        )
        if active_only:
            query = query.where(
                AcademicLevelDepartment.is_active.is_(True),
                AcademicLevelDepartment.archived_at.is_(None),
                Department.is_active.is_(True),
                Department.archived_at.is_(None),
            )
        elif not include_archived:
            query = query.where(AcademicLevelDepartment.archived_at.is_(None))
        return list((await db.execute(query.order_by(Department.name))).scalars().unique())

    @staticmethod
    async def count_dependencies(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        link_id: uuid.UUID,
    ) -> dict[str, int]:
        live_statuses = (
            AcademicTermStatus.DRAFT,
            AcademicTermStatus.OPEN,
            AcademicTermStatus.CLOSING,
        )
        class_total = (
            select(func.count())
            .select_from(ClassTermDepartmentAssignment)
            .where(
                ClassTermDepartmentAssignment.tenant_id == tenant_id,
                ClassTermDepartmentAssignment.academic_level_department_id == link_id,
            )
            .scalar_subquery()
        )
        class_live = (
            select(func.count())
            .select_from(ClassTermDepartmentAssignment)
            .join(AcademicTerm, AcademicTerm.id == ClassTermDepartmentAssignment.academic_term_id)
            .where(
                ClassTermDepartmentAssignment.tenant_id == tenant_id,
                ClassTermDepartmentAssignment.academic_level_department_id == link_id,
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.status.in_(live_statuses),
            )
            .scalar_subquery()
        )
        curriculum_links_total = (
            select(func.count())
            .select_from(CurriculumSubjectDepartment)
            .where(
                CurriculumSubjectDepartment.tenant_id == tenant_id,
                CurriculumSubjectDepartment.academic_level_department_id == link_id,
            )
            .scalar_subquery()
        )
        curriculum_links_live = (
            select(func.count())
            .select_from(CurriculumSubjectDepartment)
            .join(
                CurriculumSubject,
                CurriculumSubject.id == CurriculumSubjectDepartment.curriculum_subject_id,
            )
            .where(
                CurriculumSubjectDepartment.tenant_id == tenant_id,
                CurriculumSubjectDepartment.academic_level_department_id == link_id,
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.is_active.is_(True),
            )
            .scalar_subquery()
        )
        row = (
            await db.execute(
                select(
                    class_total.label("class_assignments_total"),
                    class_live.label("class_assignments_live"),
                    curriculum_links_total.label("curriculum_subject_links_total"),
                    curriculum_links_live.label("curriculum_subject_links_live"),
                )
            )
        ).one()
        return {
            "class_assignments_total": int(row.class_assignments_total),
            "class_assignments_live": int(row.class_assignments_live),
            "curriculum_subject_links_total": int(row.curriculum_subject_links_total),
            "curriculum_subject_links_live": int(row.curriculum_subject_links_live),
        }
