"""Dependency-aware grading-scale deletion routes."""

from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics.models import (
    AcademicLifecycleAudit,
    GradingScale,
    StudentSubjectResult,
)
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/academics/grading-scales",
    tags=["Tenant Admin Academics"],
)

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]


class GradingScaleDeleteRequest(BaseModel):
    confirmation: Literal["DELETE_GRADING_SCALE"]


class GradingScaleDependencyPreview(BaseModel):
    grading_scale_id: UUID
    result_references: int
    can_delete: bool
    blocker_messages: list[str]


async def _get_locked_scale(
    db: DbSession,
    tenant_id: UUID,
    scale_id: UUID,
) -> GradingScale:
    scale = (
        await db.execute(
            select(GradingScale)
            .where(
                GradingScale.tenant_id == tenant_id,
                GradingScale.id == scale_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if scale is None:
        raise NotFoundException("Grading scale not found.")
    return scale


async def _result_reference_count(
    db: DbSession,
    tenant_id: UUID,
    scale_id: UUID,
) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(StudentSubjectResult)
                .where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.grading_scale_id == scale_id,
                )
            )
        ).scalar_one()
    )


@router.get(
    "/{scale_id}/dependencies",
    response_model=GradingScaleDependencyPreview,
)
async def grading_scale_dependencies(
    scale_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> GradingScaleDependencyPreview:
    scale = (
        await db.execute(
            select(GradingScale).where(
                GradingScale.tenant_id == current_admin.tenant_id,
                GradingScale.id == scale_id,
            )
        )
    ).scalar_one_or_none()
    if scale is None:
        raise NotFoundException("Grading scale not found.")

    result_references = await _result_reference_count(
        db,
        current_admin.tenant_id,
        scale.id,
    )
    blockers: list[str] = []
    if scale.is_active:
        blockers.append("Deactivate this grading scale before deleting it.")
    if result_references:
        blockers.append(
            f"This grading scale is referenced by {result_references} result record(s) and must be preserved for history."
        )

    return GradingScaleDependencyPreview(
        grading_scale_id=scale.id,
        result_references=result_references,
        can_delete=not blockers,
        blocker_messages=blockers,
    )


@router.delete(
    "/{scale_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_grading_scale(
    scale_id: UUID,
    payload: GradingScaleDeleteRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> None:
    _ = payload.confirmation
    scale = await _get_locked_scale(
        db,
        current_admin.tenant_id,
        scale_id,
    )
    if scale.is_active:
        raise ConflictException(
            "Active grading scales cannot be deleted. Deactivate the scale first.",
            payload={
                "blocker_messages": [
                    "Deactivate this grading scale before deleting it."
                ]
            },
        )

    result_references = await _result_reference_count(
        db,
        current_admin.tenant_id,
        scale.id,
    )
    if result_references:
        message = (
            f"This grading scale is referenced by {result_references} result record(s) "
            "and cannot be deleted."
        )
        raise ConflictException(
            message,
            payload={
                "dependency_counts": {"result_references": result_references},
                "blocker_messages": [message],
            },
        )

    db.add(
        AcademicLifecycleAudit(
            tenant_id=current_admin.tenant_id,
            entity_type="grading_scale",
            entity_id=scale.id,
            action="delete",
            previous_status="inactive",
            new_status="deleted",
            acting_admin_id=current_admin.id,
            metadata_json={
                "grade": scale.grade,
                "min_score": str(scale.min_score),
                "max_score": str(scale.max_score),
                "remark": scale.remark,
            },
        )
    )
    await db.delete(scale)
    await db.commit()
