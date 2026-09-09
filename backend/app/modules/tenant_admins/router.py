"""Tenant-admin boundary for school-owned lifecycle operations."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.students.admin_contracts import StudentAdminContractService
from app.modules.students.creation_service import StudentCreationService
from app.modules.students.lifecycle_service import StudentLifecycleService
from app.modules.students.models import AcademicStatus, StudentAccessCodePurpose
from app.modules.students.schemas import (
    StudentAccessCodeGenerateRequest,
    StudentAdminAccessCodeResponse,
    StudentAdminProfileUpdate,
    StudentArchiveRequest,
    StudentCreate,
    StudentDetailResponse,
    StudentExpelRequest,
    StudentGraduateRequest,
    StudentHardDeleteEligibilityResponse,
    StudentHardDeleteRequest,
    StudentLifecycleReasonRequest,
    StudentLifecycleTransitionResponse,
    StudentListResponse,
    StudentParentLinkRequestDecision,
    StudentParentLinkRequestResponse,
    StudentParentLinkResponse,
    StudentParentLinkUpdateRequest,
    StudentReinstateRequest,
    StudentReturnEnrollmentRequest,
    StudentRestoreFromArchiveRequest,
    StudentSuspendRequest,
    StudentWithdrawRequest,
)
from app.modules.students.service import (
    StudentAccessCodeService,
    StudentParentLinkRequestService,
    StudentParentLinkService,
    StudentService,
)
from app.modules.subscriptions.quota_lock import acquire_resource_quota_lock
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import ResourceLimitCode
from app.modules.tenant_admins.models import TenantAdmin
from app.modules.tenant_admins.service import TenantAdminService
from app.tenant_management.schemas import TenantOnboardingStatusResponse, TenantOnboardingUpdate
from app.tenant_management.service import TenantService

router = APIRouter()
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.get("/onboarding-status", response_model=TenantOnboardingStatusResponse)
async def get_tenant_admin_onboarding_status(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TenantOnboardingStatusResponse:
    return await TenantService.get_tenant_onboarding_status(db, current_admin.tenant_id)


@router.patch("/tenant/onboarding", response_model=TenantOnboardingStatusResponse)
async def complete_tenant_admin_onboarding(
    payload: TenantOnboardingUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TenantOnboardingStatusResponse:
    await TenantService.update_tenant_onboarding(db, current_admin.tenant_id, payload)
    return await TenantService.get_tenant_onboarding_status(db, current_admin.tenant_id)


@router.get("/analytics/overview")
async def get_tenant_admin_analytics_overview(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> dict[str, object]:
    return await TenantAdminService.get_analytics_overview(
        db,
        tenant_id=current_admin.tenant_id,
    )


@router.post("/students", response_model=StudentDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentDetailResponse:
    await acquire_resource_quota_lock(
        db,
        tenant_id=current_admin.tenant_id,
        resource=ResourceLimitCode.STUDENTS,
    )
    await SubscriptionFeatureService.ensure_resource_limit_available(
        db,
        current_admin.tenant_id,
        ResourceLimitCode.STUDENTS,
    )
    student = await StudentCreationService.create_student_profile(db, current_admin, payload)
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_admin.tenant_id)
    return student


@router.get("/students", response_model=StudentListResponse)
async def list_students(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    class_id: UUID | None = Query(default=None),
    academic_level_id: UUID | None = Query(default=None),
    unassigned_class: bool = Query(default=False),
    status_filter: AcademicStatus | None = Query(default=None, alias="status"),
    include_archived: bool = Query(default=False),
) -> StudentListResponse:
    students, total = await StudentAdminContractService.list_students(
        db,
        actor=current_admin,
        skip=skip,
        limit=limit,
        search=search,
        class_id=class_id,
        academic_level_id=academic_level_id,
        unassigned_class=unassigned_class,
        status=status_filter,
        include_archived=include_archived,
    )
    return StudentListResponse(items=students, total=total)


@router.get("/students/{student_id}", response_model=StudentDetailResponse)
async def get_student(
    student_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentDetailResponse:
    return await StudentAdminContractService.get_student(
        db, actor=current_admin, student_id=student_id
    )


@router.patch("/students/{student_id}/profile", response_model=StudentDetailResponse)
async def update_student_profile(
    student_id: UUID,
    payload: StudentAdminProfileUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentDetailResponse:
    return await StudentAdminContractService.update_profile(
        db,
        actor=current_admin,
        student_id=student_id,
        payload=payload,
    )


@router.post(
    "/students/{student_id}/access-codes",
    response_model=StudentAdminAccessCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_student_access_code(
    student_id: UUID,
    payload: StudentAccessCodeGenerateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentAdminAccessCodeResponse:
    return await StudentAccessCodeService.generate_for_admin(
        db,
        actor=current_admin,
        student_id=student_id,
        purpose=StudentAccessCodePurpose(payload.purpose),
    )


@router.post("/students/{student_id}/suspend", response_model=StudentLifecycleTransitionResponse)
async def suspend_student(
    student_id: UUID,
    payload: StudentSuspendRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.suspend(
        db,
        actor=current_admin,
        student_id=student_id,
        reason=payload.reason,
        promotion_hold=payload.promotion_hold,
    )


@router.post("/students/{student_id}/reinstate", response_model=StudentLifecycleTransitionResponse)
async def reinstate_suspended_student(
    student_id: UUID,
    payload: StudentReinstateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.reinstate(
        db,
        actor=current_admin,
        student_id=student_id,
        reason=payload.reason,
    )


@router.post(
    "/students/{student_id}/reinstate-expelled",
    response_model=StudentLifecycleTransitionResponse,
)
async def reinstate_expelled_student(
    student_id: UUID,
    payload: StudentReturnEnrollmentRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.reinstate_expelled(
        db,
        actor=current_admin,
        student_id=student_id,
        payload=payload,
    )


@router.post("/students/{student_id}/readmit", response_model=StudentLifecycleTransitionResponse)
async def readmit_withdrawn_student(
    student_id: UUID,
    payload: StudentReturnEnrollmentRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.readmit(
        db, actor=current_admin, student_id=student_id, payload=payload
    )


@router.post(
    "/students/{student_id}/re-enrol-graduate",
    response_model=StudentLifecycleTransitionResponse,
)
async def reenrol_graduated_student(
    student_id: UUID,
    payload: StudentReturnEnrollmentRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.reenrol_graduate(
        db, actor=current_admin, student_id=student_id, payload=payload
    )


@router.post("/students/{student_id}/withdraw", response_model=StudentLifecycleTransitionResponse)
async def withdraw_student(
    student_id: UUID,
    payload: StudentWithdrawRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.withdraw(
        db,
        actor=current_admin,
        student_id=student_id,
        reason=payload.reason,
        effective_date=payload.effective_date,
    )


@router.post("/students/{student_id}/expel", response_model=StudentLifecycleTransitionResponse)
async def expel_student(
    student_id: UUID,
    payload: StudentExpelRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.expel(
        db,
        actor=current_admin,
        student_id=student_id,
        reason=payload.reason,
        effective_date=payload.effective_date,
    )


@router.post("/students/{student_id}/graduate", response_model=StudentLifecycleTransitionResponse)
async def graduate_student(
    student_id: UUID,
    payload: StudentGraduateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.graduate(
        db,
        actor=current_admin,
        student_id=student_id,
        reason=payload.reason,
        graduation_date=payload.graduation_date,
    )


@router.post(
    "/students/{student_id}/undo-withdrawal",
    response_model=StudentLifecycleTransitionResponse,
)
async def undo_student_withdrawal(
    student_id: UUID,
    payload: StudentLifecycleReasonRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.undo_withdrawal(
        db, actor=current_admin, student_id=student_id, reason=payload.reason
    )


@router.post(
    "/students/{student_id}/undo-expulsion",
    response_model=StudentLifecycleTransitionResponse,
)
async def undo_student_expulsion(
    student_id: UUID,
    payload: StudentLifecycleReasonRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.undo_expulsion(
        db, actor=current_admin, student_id=student_id, reason=payload.reason
    )


@router.post(
    "/students/{student_id}/undo-graduation",
    response_model=StudentLifecycleTransitionResponse,
)
async def undo_student_graduation(
    student_id: UUID,
    payload: StudentLifecycleReasonRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentLifecycleTransitionResponse:
    return await StudentLifecycleService.undo_graduation(
        db, actor=current_admin, student_id=student_id, reason=payload.reason
    )


@router.post("/students/{student_id}/archive", response_model=StudentDetailResponse)
async def archive_student(
    student_id: UUID,
    payload: StudentArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentDetailResponse:
    return await StudentLifecycleService.archive(
        db,
        actor=current_admin,
        student_id=student_id,
        reason=payload.reason,
    )


@router.post("/students/{student_id}/restore", response_model=StudentDetailResponse)
async def restore_student(
    student_id: UUID,
    payload: StudentRestoreFromArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentDetailResponse:
    student = await StudentLifecycleService.restore(
        db,
        actor=current_admin,
        student_id=student_id,
        reason=payload.reason,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_admin.tenant_id)
    return student


@router.get(
    "/students/{student_id}/hard-delete-eligibility",
    response_model=StudentHardDeleteEligibilityResponse,
)
async def get_student_hard_delete_eligibility(
    student_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentHardDeleteEligibilityResponse:
    return await StudentLifecycleService.hard_delete_eligibility(
        db,
        tenant_id=current_admin.tenant_id,
        student_id=student_id,
    )


@router.post("/students/{student_id}/hard-delete", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_unused_student(
    student_id: UUID,
    payload: StudentHardDeleteRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> None:
    _ = payload.reason
    await StudentLifecycleService.hard_delete(db, actor=current_admin, student_id=student_id)
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_admin.tenant_id)


@router.patch("/student-parent-links/{link_id}", response_model=StudentParentLinkResponse)
async def update_student_parent_link(
    link_id: UUID,
    payload: StudentParentLinkUpdateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentParentLinkResponse:
    return await StudentParentLinkService.update(
        db,
        actor=current_admin,
        link_id=link_id,
        payload=payload,
    )


@router.post(
    "/student-parent-link-requests/{request_id}/decision",
    response_model=StudentParentLinkRequestResponse,
)
async def decide_student_parent_link_request(
    request_id: UUID,
    payload: StudentParentLinkRequestDecision,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentParentLinkRequestResponse:
    return await StudentParentLinkRequestService.respond_to_request(
        db,
        current_admin,
        request_id,
        payload,
    )
