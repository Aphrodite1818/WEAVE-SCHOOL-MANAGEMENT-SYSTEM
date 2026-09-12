"""Protect an open term from structural changes that would invalidate specialization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException
from app.modules.classes.department_repository import AcademicLevelDepartmentRepository
from app.modules.classes.models import AcademicLevel, AcademicLevelDepartment
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.models import AcademicTerm, AcademicTermStatus


@dataclass(frozen=True, slots=True)
class CurrentTermDepartmentRequirement:
    term: AcademicTerm
    department_link: AcademicLevelDepartment
    assignment_exists: bool = False


class CurrentTermStructureIntegrity:
    """Validate the exact-term department requirement before a class becomes active."""

    @staticmethod
    async def current_open_term(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
    ) -> AcademicTerm | None:
        return (
            await db.execute(
                select(AcademicTerm)
                .where(
                    AcademicTerm.tenant_id == tenant_id,
                    AcademicTerm.is_current.is_(True),
                    AcademicTerm.status == AcademicTermStatus.OPEN,
                )
                .limit(1)
            )
        ).scalar_one_or_none()

    @staticmethod
    def _term_label(term: AcademicTerm) -> str:
        value = getattr(term.name, "value", str(term.name))
        return str(value).replace("_", " ").title()

    @staticmethod
    async def _validated_requested_department(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        level: AcademicLevel,
        department_link_id: uuid.UUID,
    ) -> AcademicLevelDepartment:
        link = await AcademicLevelDepartmentRepository.get_by_id(
            db,
            tenant_id,
            department_link_id,
            lock=True,
        )
        if link is None or link.academic_level_id != level.id:
            raise ConflictException(
                "The selected department is not available for this academic level."
            )
        if (
            not link.is_active
            or link.archived_at is not None
            or not link.department.is_active
            or link.department.archived_at is not None
        ):
            raise ConflictException(
                "The selected department must be active for this academic level."
            )
        return link

    @staticmethod
    async def requirement_for_active_class(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        level: AcademicLevel,
        class_id: uuid.UUID | None = None,
        requested_department_link_id: uuid.UUID | None = None,
    ) -> CurrentTermDepartmentRequirement | None:
        term = await CurrentTermStructureIntegrity.current_open_term(
            db,
            tenant_id=tenant_id,
        )
        if term is None:
            if requested_department_link_id is not None:
                raise BadRequestException(
                    "A current-term department can only be supplied while an academic term is open."
                )
            return None

        if not CurriculumResolutionService.specialization_is_active(level, term):
            if requested_department_link_id is not None:
                raise BadRequestException(
                    f"{level.name} does not require department specialization in "
                    f"{CurrentTermStructureIntegrity._term_label(term)}."
                )
            return None

        active_links = await AcademicLevelDepartmentRepository.list_for_level(
            db,
            tenant_id,
            level.id,
            active_only=True,
        )
        if not active_links:
            raise ConflictException(
                f"{level.name} requires department specialization in "
                f"{CurrentTermStructureIntegrity._term_label(term)}, but no active departments "
                "are configured for this level. Configure level departments before making a class active.",
                payload={
                    "code": "CURRENT_TERM_SPECIALIZATION_DEPARTMENTS_REQUIRED",
                    "academic_level_id": str(level.id),
                    "academic_term_id": str(term.id),
                    "departments_available": 0,
                },
            )

        existing_assignment = None
        if class_id is not None:
            existing_assignment = (
                await db.execute(
                    select(ClassTermDepartmentAssignment).where(
                        ClassTermDepartmentAssignment.tenant_id == tenant_id,
                        ClassTermDepartmentAssignment.class_id == class_id,
                        ClassTermDepartmentAssignment.academic_term_id == term.id,
                    )
                )
            ).scalar_one_or_none()

        if existing_assignment is not None:
            existing_link = await CurrentTermStructureIntegrity._validated_requested_department(
                db,
                tenant_id=tenant_id,
                level=level,
                department_link_id=existing_assignment.academic_level_department_id,
            )
            if (
                requested_department_link_id is not None
                and requested_department_link_id != existing_link.id
            ):
                raise ConflictException(
                    "This class already has a department for the current term. Change it from "
                    "Class Specializations so academic-evidence protections are applied."
                )
            return CurrentTermDepartmentRequirement(
                term=term,
                department_link=existing_link,
                assignment_exists=True,
            )

        if requested_department_link_id is None:
            raise ConflictException(
                f"Choose a department for {CurrentTermStructureIntegrity._term_label(term)} before "
                f"making a {level.name} class active.",
                payload={
                    "code": "CURRENT_TERM_SPECIALIZATION_SELECTION_REQUIRED",
                    "academic_level_id": str(level.id),
                    "academic_term_id": str(term.id),
                    "departments_available": len(active_links),
                },
            )

        requested_link = await CurrentTermStructureIntegrity._validated_requested_department(
            db,
            tenant_id=tenant_id,
            level=level,
            department_link_id=requested_department_link_id,
        )
        return CurrentTermDepartmentRequirement(
            term=term,
            department_link=requested_link,
            assignment_exists=False,
        )

    @staticmethod
    def add_assignment(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        admin_id: uuid.UUID,
        requirement: CurrentTermDepartmentRequirement | None,
    ) -> None:
        if requirement is None or requirement.assignment_exists:
            return
        db.add(
            ClassTermDepartmentAssignment(
                tenant_id=tenant_id,
                class_id=class_id,
                academic_term_id=requirement.term.id,
                academic_level_department_id=requirement.department_link.id,
                assigned_by_admin_id=admin_id,
            )
        )
