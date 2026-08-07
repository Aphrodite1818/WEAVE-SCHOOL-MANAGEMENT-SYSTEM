"""Routes for authenticated legal compliance acceptance."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_actor
from app.modules.legal_compliance.schemas import (
    LegalComplianceAcceptanceResponse,
    LegalComplianceStatusResponse,
)
from app.modules.legal_compliance.service import LegalComplianceService
from app.modules.parents.models import Parent, ParentAccount
from app.modules.students.models import Student
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher, TeacherAccount
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(prefix="/legal-compliance", tags=["Legal Compliance"])

CurrentActor = Annotated[
    SuperAdmin
    | TenantAdmin
    | Teacher
    | Parent
    | Student
    | TeacherAccount
    | ParentAccount,
    Depends(get_current_actor),
]


@router.get("/status", response_model=LegalComplianceStatusResponse)
async def get_legal_compliance_status(
    db: DbSession,
    current_actor: CurrentActor,
) -> dict[str, object]:
    return await LegalComplianceService.get_status(db, current_actor)


@router.post("/accept", response_model=LegalComplianceAcceptanceResponse)
async def accept_legal_compliance(
    db: DbSession,
    current_actor: CurrentActor,
) -> dict[str, object]:
    status = await LegalComplianceService.accept(db, current_actor)
    return {**status, "detail": "Legal compliance terms accepted."}
