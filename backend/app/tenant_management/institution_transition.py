"""Safe institution-type transition planning and execution.

Changing institution type changes the academic category catalogue. Established
academic evidence is therefore never rewritten or deleted. Only genuinely
disposable draft setup can be reset, and that reset is explicit and atomic.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelDepartment,
    AcademicLevelStatus,
    ClassRoom,
    Department,
)
from app.modules.student_academics.curriculum_models import Curriculum
from app.modules.students.models import StudentEnrollment
from app.tenant_management.models import InstitutionType, Tenant
from app.tenant_management.repository import TenantRepository

RESET_CONFIRMATION = "RESET_ACADEMIC_STRUCTURE"


class InstitutionTypeTransitionMode(StrEnum):
    DIRECT = "DIRECT"
    RESET_REQUIRED = "RESET_REQUIRED"
    BLOCKED = "BLOCKED"


class InstitutionTypeTransitionRequest(BaseModel):
    institution_type: InstitutionType
    confirmation: Literal["RESET_ACADEMIC_STRUCTURE"] | None = None


class InstitutionTypeTransitionPreview(BaseModel):
    current_type: InstitutionType | None
    requested_type: InstitutionType
    mode: InstitutionTypeTransitionMode
    reset_counts: dict[str, int]
    blocker_counts: dict[str, int]
    blocker_messages: list[str]
    confirmation_text: str | None = None


class InstitutionTypeTransitionResult(BaseModel):
    transition: InstitutionTypeTransitionPreview
    tenant_id: uuid.UUID
    institution_type: InstitutionType


class InstitutionTypeTransitionService:
    """Classify and apply institution-type changes without destroying evidence."""

    @staticmethod
    async def _count(db: AsyncSession, model, tenant_id: uuid.UUID) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
                )
            ).scalar_one()
        )

    @staticmethod
    async def _inspect(
        db: AsyncSession,
        *,
        tenant: Tenant,
        requested_type: InstitutionType,
        lock: bool,
    ) -> InstitutionTypeTransitionPreview:
        level_query = select(AcademicLevel).where(AcademicLevel.tenant_id == tenant.id)
        department_query = select(Department).where(Department.tenant_id == tenant.id)
        if lock:
            level_query = level_query.with_for_update()
            department_query = department_query.with_for_update()

        levels = list((await db.execute(level_query)).scalars())
        departments = list((await db.execute(department_query)).scalars())

        counts = {
            "academic_levels": len(levels),
            "departments": len(departments),
            "classes": await InstitutionTypeTransitionService._count(db, ClassRoom, tenant.id),
            "level_department_links": await InstitutionTypeTransitionService._count(
                db, AcademicLevelDepartment, tenant.id
            ),
            "curricula": await InstitutionTypeTransitionService._count(db, Curriculum, tenant.id),
            "student_enrollments": await InstitutionTypeTransitionService._count(
                db, StudentEnrollment, tenant.id
            ),
            "published_levels": sum(
                1 for level in levels if level.status != AcademicLevelStatus.DRAFT
            ),
        }

        reset_counts = {
            "academic_levels": counts["academic_levels"],
            "departments": counts["departments"],
        }

        if tenant.institution_type == requested_type:
            return InstitutionTypeTransitionPreview(
                current_type=tenant.institution_type,
                requested_type=requested_type,
                mode=InstitutionTypeTransitionMode.DIRECT,
                reset_counts={"academic_levels": 0, "departments": 0},
                blocker_counts={},
                blocker_messages=[],
            )

        protected_keys = (
            "published_levels",
            "classes",
            "level_department_links",
            "curricula",
            "student_enrollments",
        )
        blocker_counts = {key: counts[key] for key in protected_keys if counts[key] > 0}
        blocker_messages: list[str] = []
        if counts["published_levels"]:
            blocker_messages.append(
                "One or more academic levels have left draft status and are protected."
            )
        if counts["classes"]:
            blocker_messages.append("Classes already depend on the academic level structure.")
        if counts["level_department_links"]:
            blocker_messages.append("Department-to-level mappings already exist.")
        if counts["curricula"]:
            blocker_messages.append("Curriculum configuration already depends on academic levels.")
        if counts["student_enrollments"]:
            blocker_messages.append(
                "Student enrollment history already references the academic structure."
            )

        if blocker_messages:
            mode = InstitutionTypeTransitionMode.BLOCKED
            confirmation_text = None
        elif levels or departments:
            mode = InstitutionTypeTransitionMode.RESET_REQUIRED
            confirmation_text = RESET_CONFIRMATION
        else:
            mode = InstitutionTypeTransitionMode.DIRECT
            confirmation_text = None
            reset_counts = {"academic_levels": 0, "departments": 0}

        return InstitutionTypeTransitionPreview(
            current_type=tenant.institution_type,
            requested_type=requested_type,
            mode=mode,
            reset_counts=reset_counts,
            blocker_counts=blocker_counts,
            blocker_messages=blocker_messages,
            confirmation_text=confirmation_text,
        )

    @staticmethod
    async def preview(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        requested_type: InstitutionType,
    ) -> InstitutionTypeTransitionPreview:
        tenant = await TenantRepository.get_by_id(db, tenant_id)
        if tenant is None:
            raise NotFoundException("Tenant not found")
        return await InstitutionTypeTransitionService._inspect(
            db,
            tenant=tenant,
            requested_type=requested_type,
            lock=False,
        )

    @staticmethod
    async def apply(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: InstitutionTypeTransitionRequest,
    ) -> InstitutionTypeTransitionResult:
        try:
            tenant = await TenantRepository.get_by_id(db, tenant_id, lock=True)
            if tenant is None:
                raise NotFoundException("Tenant not found")

            preview = await InstitutionTypeTransitionService._inspect(
                db,
                tenant=tenant,
                requested_type=payload.institution_type,
                lock=True,
            )

            if preview.mode == InstitutionTypeTransitionMode.BLOCKED:
                raise ConflictException(
                    "Institution type cannot be changed because protected academic evidence exists.",
                    payload=preview.model_dump(mode="json"),
                )

            if preview.mode == InstitutionTypeTransitionMode.RESET_REQUIRED:
                if payload.confirmation != RESET_CONFIRMATION:
                    raise ConflictException(
                        f"Type {RESET_CONFIRMATION} to confirm the disposable academic setup reset.",
                        payload=preview.model_dump(mode="json"),
                    )

                levels = list(
                    (
                        await db.execute(
                            select(AcademicLevel)
                            .where(AcademicLevel.tenant_id == tenant_id)
                            .with_for_update()
                        )
                    ).scalars()
                )
                departments = list(
                    (
                        await db.execute(
                            select(Department)
                            .where(Department.tenant_id == tenant_id)
                            .with_for_update()
                        )
                    ).scalars()
                )
                for level in levels:
                    await db.delete(level)
                for department in departments:
                    await db.delete(department)
                await db.flush()

            tenant.institution_type = payload.institution_type
            db.add(tenant)
            await db.commit()
            await db.refresh(tenant)

            return InstitutionTypeTransitionResult(
                transition=preview,
                tenant_id=tenant.id,
                institution_type=tenant.institution_type,
            )
        except Exception:
            await db.rollback()
            raise
