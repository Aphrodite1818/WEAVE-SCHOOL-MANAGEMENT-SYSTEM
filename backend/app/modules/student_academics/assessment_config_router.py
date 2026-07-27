"""Tenant assessment-component configuration routes."""

from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.student_academics.models import SchoolAssessmentConfig
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/academics/assessment-config",
    tags=["Tenant Admin Academics"],
)

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin,
    Depends(get_current_tenant_admin),
]


class AssessmentConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    test_max: int
    assessment_max: int
    exam_max: int


class AssessmentConfigUpdate(BaseModel):
    test_max: int = Field(gt=0, le=100)
    assessment_max: int = Field(gt=0, le=100)
    exam_max: int = Field(gt=0, le=100)

    @model_validator(mode="after")
    def validate_total(self):
        if self.test_max + self.assessment_max + self.exam_max != 100:
            raise ValueError("Assessment component maximums must total 100.")
        return self


async def _get_or_create_config(
    db: DbSession,
    tenant_id,
    *,
    lock: bool = False,
) -> SchoolAssessmentConfig:
    query = select(SchoolAssessmentConfig).where(
        SchoolAssessmentConfig.tenant_id == tenant_id
    )
    if lock:
        query = query.with_for_update()
    config = (await db.execute(query)).scalar_one_or_none()
    if config is None:
        config = SchoolAssessmentConfig(
            tenant_id=tenant_id,
            test_max=20,
            assessment_max=20,
            exam_max=60,
        )
        db.add(config)
        await db.flush()
    return config


@router.get("", response_model=AssessmentConfigResponse)
async def get_assessment_config(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AssessmentConfigResponse:
    config = await _get_or_create_config(db, current_admin.tenant_id)
    await db.commit()
    return AssessmentConfigResponse.model_validate(config)


@router.patch("", response_model=AssessmentConfigResponse)
async def update_assessment_config(
    payload: AssessmentConfigUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AssessmentConfigResponse:
    config = await _get_or_create_config(
        db,
        current_admin.tenant_id,
        lock=True,
    )
    config.test_max = payload.test_max
    config.assessment_max = payload.assessment_max
    config.exam_max = payload.exam_max
    await db.flush()
    await db.commit()
    await db.refresh(config)
    return AssessmentConfigResponse.model_validate(config)
