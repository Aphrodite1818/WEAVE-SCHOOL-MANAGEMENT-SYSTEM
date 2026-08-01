"""Role-specific attendance and geofencing routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_parent,
    get_current_student,
    get_current_teacher,
    get_current_tenant_admin,
)
from app.core.exceptions import ForbiddenException, NotFoundException
from app.modules.attendance.attendance_enums import (
    AttendanceActorType,
    AttendanceCorrectionStatus,
    SchoolGeofenceStatus,
    StudentAttendanceSheetStatus,
)
from app.modules.attendance.schemas import (
    AttendanceAnalyticsResponse,
    AttendanceCorrectionCreate,
    AttendanceCorrectionListResponse,
    AttendanceCorrectionResponse,
    AttendanceCorrectionReview,
    AttendanceReadinessResponse,
    AttendanceSettingsResponse,
    AttendanceSettingsUpdate,
    GeofenceEvaluationResponse,
    GeofencePreviewRequest,
    SchoolGeofenceCreate,
    SchoolGeofenceListResponse,
    SchoolGeofenceResponse,
    SchoolGeofenceUpdate,
    StudentAttendanceBulkMarkRequest,
    StudentAttendanceRecordListResponse,
    StudentAttendanceSheetListResponse,
    StudentAttendanceSheetOpenRequest,
    StudentAttendanceSheetResponse,
    StudentAttendanceSheetSubmitRequest,
    TemporaryAttendanceAssignmentCreate,
    TemporaryAttendanceAssignmentResponse,
    WorkforceAttendanceListResponse,
    WorkforceAttendanceResponse,
    WorkforceCheckInRequest,
    WorkforceCheckOutRequest,
)
from app.modules.attendance.service import (
    AttendanceAdminService,
    AttendanceAnalyticsService,
    AttendanceSettingsService,
    GeofenceService,
    StudentAttendanceService,
    WorkforceAttendanceService,
)
from app.modules.parents.models import Parent
from app.modules.students.models import Student, StudentParentLink, StudentParentLinkStatus
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


tenant_admin_router = APIRouter(prefix="/tenant-admin/attendance", tags=["Tenant Admin Attendance"])
teacher_router = APIRouter(prefix="/teacher/attendance", tags=["Teacher Attendance"])
student_router = APIRouter(prefix="/student/attendance", tags=["Student Attendance"])
parent_router = APIRouter(prefix="/parent/attendance", tags=["Parent Attendance"])

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTeacher: TypeAlias = Annotated[Teacher, Depends(get_current_teacher)]
CurrentStudent: TypeAlias = Annotated[Student, Depends(get_current_student)]
CurrentParent: TypeAlias = Annotated[Parent, Depends(get_current_parent)]


async def _ensure_attendance(db: DbSession, tenant_id: UUID) -> None:
    await SubscriptionFeatureService.ensure_feature_enabled(db, tenant_id, FeatureCode.ATTENDANCE)


async def _ensure_geofencing(db: DbSession, tenant_id: UUID) -> None:
    await SubscriptionFeatureService.ensure_feature_enabled(db, tenant_id, FeatureCode.GEOFENCING)


@tenant_admin_router.get("/settings", response_model=AttendanceSettingsResponse)
async def admin_get_settings(db: DbSession, current_admin: CurrentTenantAdmin) -> AttendanceSettingsResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await AttendanceSettingsService.response(db, current_admin.tenant_id)


@tenant_admin_router.put("/settings", response_model=AttendanceSettingsResponse)
async def admin_update_settings(
    payload: AttendanceSettingsUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AttendanceSettingsResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await AttendanceSettingsService.update(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.get("/geofences", response_model=SchoolGeofenceListResponse)
async def admin_list_geofences(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    include_archived: bool = Query(default=False),
) -> SchoolGeofenceListResponse:
    await _ensure_geofencing(db, current_admin.tenant_id)
    return await GeofenceService.list_geofences(db, current_admin.tenant_id, include_archived=include_archived)


@tenant_admin_router.post("/geofences", response_model=SchoolGeofenceResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_geofence(
    payload: SchoolGeofenceCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolGeofenceResponse:
    await _ensure_geofencing(db, current_admin.tenant_id)
    return await GeofenceService.create_geofence(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.patch("/geofences/{geofence_id}", response_model=SchoolGeofenceResponse)
async def admin_update_geofence(
    geofence_id: UUID,
    payload: SchoolGeofenceUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolGeofenceResponse:
    await _ensure_geofencing(db, current_admin.tenant_id)
    return await GeofenceService.update_geofence(
        db,
        tenant_id=current_admin.tenant_id,
        geofence_id=geofence_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.post("/geofences/{geofence_id}/activate", response_model=SchoolGeofenceResponse)
async def admin_activate_geofence(geofence_id: UUID, db: DbSession, current_admin: CurrentTenantAdmin) -> SchoolGeofenceResponse:
    await _ensure_geofencing(db, current_admin.tenant_id)
    return await GeofenceService.set_geofence_status(
        db,
        tenant_id=current_admin.tenant_id,
        geofence_id=geofence_id,
        status=SchoolGeofenceStatus.ACTIVE,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.post("/geofences/{geofence_id}/deactivate", response_model=SchoolGeofenceResponse)
async def admin_deactivate_geofence(geofence_id: UUID, db: DbSession, current_admin: CurrentTenantAdmin) -> SchoolGeofenceResponse:
    await _ensure_geofencing(db, current_admin.tenant_id)
    return await GeofenceService.set_geofence_status(
        db,
        tenant_id=current_admin.tenant_id,
        geofence_id=geofence_id,
        status=SchoolGeofenceStatus.INACTIVE,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.post("/geofences/{geofence_id}/archive", response_model=SchoolGeofenceResponse)
async def admin_archive_geofence(geofence_id: UUID, db: DbSession, current_admin: CurrentTenantAdmin) -> SchoolGeofenceResponse:
    await _ensure_geofencing(db, current_admin.tenant_id)
    return await GeofenceService.set_geofence_status(
        db,
        tenant_id=current_admin.tenant_id,
        geofence_id=geofence_id,
        status=SchoolGeofenceStatus.ARCHIVED,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.post("/geofences/preview", response_model=GeofenceEvaluationResponse)
async def admin_preview_geofence(
    payload: GeofencePreviewRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> GeofenceEvaluationResponse:
    await _ensure_geofencing(db, current_admin.tenant_id)
    return await GeofenceService.preview(
        db,
        tenant_id=current_admin.tenant_id,
        actor_type=AttendanceActorType.TENANT_ADMIN,
        actor_id=current_admin.id,
        payload=payload,
    )


@tenant_admin_router.get("/student-sheets", response_model=StudentAttendanceSheetListResponse)
async def admin_list_student_sheets(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    class_id: UUID | None = Query(default=None),
    status_filter: StudentAttendanceSheetStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> StudentAttendanceSheetListResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await StudentAttendanceService.list_sheets(
        db,
        tenant_id=current_admin.tenant_id,
        start_date=start_date,
        end_date=end_date,
        class_id=class_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@tenant_admin_router.post("/student-sheets", response_model=StudentAttendanceSheetResponse, status_code=status.HTTP_201_CREATED)
async def admin_open_student_sheet(
    payload: StudentAttendanceSheetOpenRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentAttendanceSheetResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await StudentAttendanceService.open_sheet(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.patch("/student-sheets/{sheet_id}/records", response_model=StudentAttendanceSheetResponse)
async def admin_mark_student_records(
    sheet_id: UUID,
    payload: StudentAttendanceBulkMarkRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentAttendanceSheetResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await StudentAttendanceService.mark_records(
        db,
        tenant_id=current_admin.tenant_id,
        sheet_id=sheet_id,
        payload=payload,
        actor_type=AttendanceActorType.TENANT_ADMIN,
        actor_id=current_admin.id,
    )


@tenant_admin_router.post("/student-sheets/{sheet_id}/approve", response_model=StudentAttendanceSheetResponse)
async def admin_approve_student_sheet(sheet_id: UUID, db: DbSession, current_admin: CurrentTenantAdmin) -> StudentAttendanceSheetResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await StudentAttendanceService.set_admin_sheet_status(
        db,
        tenant_id=current_admin.tenant_id,
        sheet_id=sheet_id,
        status=StudentAttendanceSheetStatus.APPROVED,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.post("/student-sheets/{sheet_id}/lock", response_model=StudentAttendanceSheetResponse)
async def admin_lock_student_sheet(sheet_id: UUID, db: DbSession, current_admin: CurrentTenantAdmin) -> StudentAttendanceSheetResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await StudentAttendanceService.set_admin_sheet_status(
        db,
        tenant_id=current_admin.tenant_id,
        sheet_id=sheet_id,
        status=StudentAttendanceSheetStatus.LOCKED,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.get("/workforce", response_model=WorkforceAttendanceListResponse)
async def admin_list_workforce(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    teacher_membership_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> WorkforceAttendanceListResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await WorkforceAttendanceService.list_records(
        db,
        tenant_id=current_admin.tenant_id,
        teacher_membership_id=teacher_membership_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


@tenant_admin_router.post("/temporary-assignments", response_model=TemporaryAttendanceAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_temporary_assignment(
    payload: TemporaryAttendanceAssignmentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> TemporaryAttendanceAssignmentResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await AttendanceAdminService.create_temporary_assignment(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.get("/corrections", response_model=AttendanceCorrectionListResponse)
async def admin_list_corrections(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    status_filter: AttendanceCorrectionStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> AttendanceCorrectionListResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await AttendanceAdminService.list_corrections(
        db,
        tenant_id=current_admin.tenant_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@tenant_admin_router.post("/corrections/{correction_id}/review", response_model=AttendanceCorrectionResponse)
async def admin_review_correction(
    correction_id: UUID,
    payload: AttendanceCorrectionReview,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AttendanceCorrectionResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await AttendanceAdminService.review_correction(
        db,
        tenant_id=current_admin.tenant_id,
        correction_id=correction_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@tenant_admin_router.get("/analytics", response_model=AttendanceAnalyticsResponse)
async def admin_analytics(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    start_date: date = Query(),
    end_date: date = Query(),
) -> AttendanceAnalyticsResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await AttendanceAnalyticsService.analytics(db, tenant_id=current_admin.tenant_id, start_date=start_date, end_date=end_date)


@tenant_admin_router.get("/readiness", response_model=AttendanceReadinessResponse)
async def admin_readiness(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    start_date: date = Query(),
    end_date: date = Query(),
) -> AttendanceReadinessResponse:
    await _ensure_attendance(db, current_admin.tenant_id)
    return await AttendanceAnalyticsService.readiness(db, tenant_id=current_admin.tenant_id, start_date=start_date, end_date=end_date)


@teacher_router.get("/student-sheets", response_model=StudentAttendanceSheetListResponse)
async def teacher_list_student_sheets(
    db: DbSession,
    current_teacher: CurrentTeacher,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    class_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> StudentAttendanceSheetListResponse:
    await _ensure_attendance(db, current_teacher.tenant_id)
    return await StudentAttendanceService.list_sheets(
        db,
        tenant_id=current_teacher.tenant_id,
        start_date=start_date,
        end_date=end_date,
        class_id=class_id,
        skip=skip,
        limit=limit,
    )


@teacher_router.post("/student-sheets", response_model=StudentAttendanceSheetResponse, status_code=status.HTTP_201_CREATED)
async def teacher_open_student_sheet(
    payload: StudentAttendanceSheetOpenRequest,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> StudentAttendanceSheetResponse:
    await _ensure_attendance(db, current_teacher.tenant_id)
    return await StudentAttendanceService.open_sheet(
        db,
        tenant_id=current_teacher.tenant_id,
        payload=payload,
        teacher_membership_id=current_teacher.id,
    )


@teacher_router.patch("/student-sheets/{sheet_id}/records", response_model=StudentAttendanceSheetResponse)
async def teacher_mark_student_records(
    sheet_id: UUID,
    payload: StudentAttendanceBulkMarkRequest,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> StudentAttendanceSheetResponse:
    await _ensure_attendance(db, current_teacher.tenant_id)
    return await StudentAttendanceService.mark_records(
        db,
        tenant_id=current_teacher.tenant_id,
        sheet_id=sheet_id,
        payload=payload,
        actor_type=AttendanceActorType.TEACHER,
        actor_id=current_teacher.id,
    )


@teacher_router.post("/student-sheets/{sheet_id}/submit", response_model=StudentAttendanceSheetResponse)
async def teacher_submit_student_sheet(
    sheet_id: UUID,
    payload: StudentAttendanceSheetSubmitRequest,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> StudentAttendanceSheetResponse:
    await _ensure_attendance(db, current_teacher.tenant_id)
    return await StudentAttendanceService.submit_sheet(
        db,
        tenant_id=current_teacher.tenant_id,
        sheet_id=sheet_id,
        payload=payload,
        teacher_membership_id=current_teacher.id,
    )


@teacher_router.post("/workforce/check-in", response_model=WorkforceAttendanceResponse)
async def teacher_check_in(
    payload: WorkforceCheckInRequest,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> WorkforceAttendanceResponse:
    await _ensure_attendance(db, current_teacher.tenant_id)
    return await WorkforceAttendanceService.check_in(
        db,
        tenant_id=current_teacher.tenant_id,
        teacher_membership_id=current_teacher.id,
        payload=payload,
    )


@teacher_router.post("/workforce/check-out", response_model=WorkforceAttendanceResponse)
async def teacher_check_out(
    payload: WorkforceCheckOutRequest,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> WorkforceAttendanceResponse:
    await _ensure_attendance(db, current_teacher.tenant_id)
    return await WorkforceAttendanceService.check_out(
        db,
        tenant_id=current_teacher.tenant_id,
        teacher_membership_id=current_teacher.id,
        payload=payload,
    )


@teacher_router.get("/workforce/me", response_model=WorkforceAttendanceListResponse)
async def teacher_my_workforce_history(
    db: DbSession,
    current_teacher: CurrentTeacher,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> WorkforceAttendanceListResponse:
    await _ensure_attendance(db, current_teacher.tenant_id)
    return await WorkforceAttendanceService.list_records(
        db,
        tenant_id=current_teacher.tenant_id,
        teacher_membership_id=current_teacher.id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


@teacher_router.post("/corrections", response_model=AttendanceCorrectionResponse, status_code=status.HTTP_201_CREATED)
async def teacher_create_correction(
    payload: AttendanceCorrectionCreate,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> AttendanceCorrectionResponse:
    await _ensure_attendance(db, current_teacher.tenant_id)
    return await AttendanceAdminService.create_correction(
        db,
        tenant_id=current_teacher.tenant_id,
        payload=payload,
        actor_type=AttendanceActorType.TEACHER,
        actor_id=current_teacher.id,
    )


@student_router.get("/me", response_model=StudentAttendanceRecordListResponse)
async def student_my_attendance(
    db: DbSession,
    current_student: CurrentStudent,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> StudentAttendanceRecordListResponse:
    await _ensure_attendance(db, current_student.tenant_id)
    return await StudentAttendanceService.list_student_records(
        db,
        tenant_id=current_student.tenant_id,
        student_id=current_student.id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


async def _ensure_parent_can_view_student(db: DbSession, *, tenant_id: UUID, parent_id: UUID, student_id: UUID) -> None:
    link = (
        await db.execute(
            select(StudentParentLink).where(
                StudentParentLink.tenant_id == tenant_id,
                StudentParentLink.parent_membership_id == parent_id,
                StudentParentLink.student_id == student_id,
                StudentParentLink.status.in_(
                    [
                        StudentParentLinkStatus.ACTIVE,
                        StudentParentLinkStatus.READ_ONLY,
                        StudentParentLinkStatus.ALUMNI_READ_ONLY,
                    ]
                ),
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise ForbiddenException("You cannot view attendance for this student.")


@parent_router.get("/students/{student_id}", response_model=StudentAttendanceRecordListResponse)
async def parent_student_attendance(
    student_id: UUID,
    db: DbSession,
    current_parent: CurrentParent,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> StudentAttendanceRecordListResponse:
    await _ensure_attendance(db, current_parent.tenant_id)
    await _ensure_parent_can_view_student(
        db,
        tenant_id=current_parent.tenant_id,
        parent_id=current_parent.id,
        student_id=student_id,
    )
    return await StudentAttendanceService.list_student_records(
        db,
        tenant_id=current_parent.tenant_id,
        student_id=student_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


# Backwards-compatible empty aggregate router for imports that expect `router`.
router = APIRouter(tags=["Attendance"])
