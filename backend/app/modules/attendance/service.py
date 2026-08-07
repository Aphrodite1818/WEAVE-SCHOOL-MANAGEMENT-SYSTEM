"""Attendance business services."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.attendance.attendance_enums import (
    AttendanceActorType,
    AttendanceCorrectionStatus,
    AttendanceCorrectionTarget,
    AttendanceNotificationChannel,
    AttendanceNotificationStatus,
    GeofenceDecision,
    SchoolGeofenceStatus,
    StudentAttendanceSheetStatus,
    StudentAttendanceStatus,
    WorkforceAttendanceStatus,
)
from app.modules.attendance.geofencing import (
    GeofenceCircle,
    LocationPoint,
    evaluate_geofence,
)
from app.modules.attendance.models import (
    AttendanceAuditLog,
    AttendanceCorrection,
    AttendanceNotification,
    AttendanceSettings,
    GeofenceEvaluation,
    SchoolGeofence,
    StudentAttendanceRecord,
    StudentAttendanceSheet,
    TemporaryAttendanceAssignment,
    WorkforceAttendanceRecord,
)
from app.modules.attendance.repository import AttendanceRepository, utc_now
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
    LocationSample,
    SchoolGeofenceCreate,
    SchoolGeofenceListResponse,
    SchoolGeofenceResponse,
    SchoolGeofenceUpdate,
    StudentAttendanceBulkMarkRequest,
    StudentAttendanceRecordResponse,
    StudentAttendanceSheetListResponse,
    StudentAttendanceRecordListResponse,
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
from app.modules.school_calendar.policy_service import SchoolDayPolicyService
from app.modules.school_calendar.service import SchoolCalendarService


def _date_or_tenant_today(value: date | None, *, tenant_today: date) -> date:
    return value or tenant_today


def _model_response(model: Any, response_cls):
    return response_cls.model_validate(model)


def _actor_audit(
    *,
    tenant_id: uuid.UUID,
    actor_type: AttendanceActorType,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    details: dict[str, Any] | None = None,
) -> AttendanceAuditLog:
    return AttendanceAuditLog(
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    )


class AttendanceSettingsService:
    @staticmethod
    async def get_or_create_settings(db: AsyncSession, tenant_id: uuid.UUID) -> AttendanceSettings:
        settings = await AttendanceRepository.get_settings(db, tenant_id)
        if settings is not None:
            return settings
        settings = AttendanceSettings(tenant_id=tenant_id)
        await AttendanceRepository.save_settings(db, settings)
        await db.commit()
        return settings

    @staticmethod
    async def response(db: AsyncSession, tenant_id: uuid.UUID) -> AttendanceSettingsResponse:
        settings = await AttendanceSettingsService.get_or_create_settings(db, tenant_id)
        return AttendanceSettingsResponse.model_validate(settings)

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: AttendanceSettingsUpdate,
        acting_admin_id: uuid.UUID,
    ) -> AttendanceSettingsResponse:
        settings = await AttendanceSettingsService.get_or_create_settings(db, tenant_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(settings, key, value)
        settings.updated_by_admin_id = acting_admin_id
        settings.configuration_revision += 1
        await AttendanceRepository.save_settings(db, settings)
        await AttendanceRepository.add_audit_log(
            db,
            _actor_audit(
                tenant_id=tenant_id,
                actor_type=AttendanceActorType.TENANT_ADMIN,
                actor_id=acting_admin_id,
                action="attendance_settings.updated",
                entity_type="attendance_settings",
                entity_id=settings.id,
                details=payload.model_dump(exclude_unset=True),
            ),
        )
        await db.commit()
        return AttendanceSettingsResponse.model_validate(settings)


class GeofenceService:
    @staticmethod
    async def list_geofences(
        db: AsyncSession, tenant_id: uuid.UUID, *, include_archived: bool = False
    ) -> SchoolGeofenceListResponse:
        rows, total = await AttendanceRepository.list_geofences(
            db, tenant_id, include_archived=include_archived
        )
        return SchoolGeofenceListResponse(
            items=[SchoolGeofenceResponse.model_validate(row) for row in rows],
            total=total,
        )

    @staticmethod
    async def create_geofence(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: SchoolGeofenceCreate,
        acting_admin_id: uuid.UUID,
    ) -> SchoolGeofenceResponse:
        if payload.is_primary:
            await AttendanceRepository.clear_primary_geofence(db, tenant_id)
        geofence = SchoolGeofence(
            tenant_id=tenant_id,
            name=payload.name,
            description=payload.description,
            latitude=payload.latitude,
            longitude=payload.longitude,
            radius_m=payload.radius_m,
            is_primary=payload.is_primary,
            created_by_admin_id=acting_admin_id,
        )
        await AttendanceRepository.save_geofence(db, geofence)
        await AttendanceRepository.add_audit_log(
            db,
            _actor_audit(
                tenant_id=tenant_id,
                actor_type=AttendanceActorType.TENANT_ADMIN,
                actor_id=acting_admin_id,
                action="geofence.created",
                entity_type="school_geofence",
                entity_id=geofence.id,
            ),
        )
        await db.commit()
        return SchoolGeofenceResponse.model_validate(geofence)

    @staticmethod
    async def update_geofence(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        geofence_id: uuid.UUID,
        payload: SchoolGeofenceUpdate,
        acting_admin_id: uuid.UUID,
    ) -> SchoolGeofenceResponse:
        geofence = await AttendanceRepository.get_geofence(db, tenant_id, geofence_id, lock=True)
        if geofence is None:
            raise NotFoundException("Geofence not found.")
        if geofence.status == SchoolGeofenceStatus.ARCHIVED:
            raise ConflictException("Archived geofences cannot be edited.")
        if payload.is_primary:
            await AttendanceRepository.clear_primary_geofence(db, tenant_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(geofence, key, value)
        await AttendanceRepository.save_geofence(db, geofence)
        await AttendanceRepository.add_audit_log(
            db,
            _actor_audit(
                tenant_id=tenant_id,
                actor_type=AttendanceActorType.TENANT_ADMIN,
                actor_id=acting_admin_id,
                action="geofence.updated",
                entity_type="school_geofence",
                entity_id=geofence.id,
                details=payload.model_dump(exclude_unset=True),
            ),
        )
        await db.commit()
        return SchoolGeofenceResponse.model_validate(geofence)

    @staticmethod
    async def set_geofence_status(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        geofence_id: uuid.UUID,
        status: SchoolGeofenceStatus,
        acting_admin_id: uuid.UUID,
    ) -> SchoolGeofenceResponse:
        geofence = await AttendanceRepository.get_geofence(db, tenant_id, geofence_id, lock=True)
        if geofence is None:
            raise NotFoundException("Geofence not found.")
        geofence.status = status
        if status != SchoolGeofenceStatus.ACTIVE:
            geofence.is_primary = False
        if status == SchoolGeofenceStatus.ARCHIVED:
            geofence.archived_at = utc_now()
            geofence.archived_by_admin_id = acting_admin_id
        await AttendanceRepository.save_geofence(db, geofence)
        await db.commit()
        return SchoolGeofenceResponse.model_validate(geofence)

    @staticmethod
    async def evaluate(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        actor_type: AttendanceActorType,
        actor_id: uuid.UUID,
        location: LocationSample | None,
        purpose: str,
        geofence_id: uuid.UUID | None = None,
        persist: bool = True,
    ) -> GeofenceEvaluationResponse:
        settings = await AttendanceSettingsService.get_or_create_settings(db, tenant_id)
        geofence = await AttendanceRepository.get_active_geofence(db, tenant_id, geofence_id)
        result = evaluate_geofence(
            geofence=(
                None
                if geofence is None
                else GeofenceCircle(
                    latitude=geofence.latitude,
                    longitude=geofence.longitude,
                    radius_m=geofence.radius_m,
                )
            ),
            location=(
                None
                if location is None
                else LocationPoint(
                    latitude=location.latitude,
                    longitude=location.longitude,
                    accuracy_m=location.accuracy_m,
                )
            ),
            max_accuracy_m=settings.geofence_accuracy_threshold_m,
            tolerance_m=settings.geofence_tolerance_m,
        )
        evaluation = GeofenceEvaluation(
            tenant_id=tenant_id,
            geofence_id=None if geofence is None else geofence.id,
            actor_type=actor_type,
            actor_id=actor_id,
            purpose=purpose,
            decision=result.decision,
            distance_m=result.distance_m,
            accuracy_m=result.accuracy_m,
            tolerance_m=result.tolerance_m,
            provided_at=None if location is None else location.provided_at,
            latitude_raw=None if location is None else location.latitude,
            longitude_raw=None if location is None else location.longitude,
            raw_location_expires_at=utc_now()
            + timedelta(days=settings.location_raw_retention_days),
            evidence_expires_at=utc_now()
            + timedelta(days=settings.location_evidence_retention_days),
            device_context=None if location is None else location.device_context,
            reason=result.reason,
        )
        if persist:
            await AttendanceRepository.save_geofence_evaluation(db, evaluation)
            await db.commit()
        return GeofenceEvaluationResponse.model_validate(evaluation)

    @staticmethod
    async def preview(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        actor_type: AttendanceActorType,
        actor_id: uuid.UUID,
        payload: GeofencePreviewRequest,
    ) -> GeofenceEvaluationResponse:
        return await GeofenceService.evaluate(
            db,
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor_id,
            location=payload.location,
            purpose=payload.purpose,
            geofence_id=payload.geofence_id,
            persist=True,
        )


class StudentAttendanceService:
    @staticmethod
    async def open_sheet(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: StudentAttendanceSheetOpenRequest,
        teacher_membership_id: uuid.UUID | None = None,
        acting_admin_id: uuid.UUID | None = None,
    ) -> StudentAttendanceSheetResponse:
        target_date = _date_or_tenant_today(
            payload.attendance_date,
            tenant_today=await SchoolCalendarService.tenant_today(db, tenant_id),
        )
        resolved = await SchoolDayPolicyService().require_student_attendance_day(
            db, tenant_id=tenant_id, target_date=target_date
        )
        classroom = await AttendanceRepository.get_class(db, tenant_id, payload.class_id)
        if classroom is None:
            raise NotFoundException("Class not found.")
        if teacher_membership_id is not None:
            allowed_classes = await AttendanceRepository.list_teacher_class_ids(
                db,
                tenant_id,
                teacher_membership_id=teacher_membership_id,
                target_date=target_date,
            )
            if payload.class_id not in allowed_classes:
                raise ForbiddenException("You are not assigned to take attendance for this class.")
        existing = await AttendanceRepository.get_sheet_by_class_date(
            db,
            tenant_id,
            class_id=payload.class_id,
            attendance_date=target_date,
        )
        if existing is not None:
            return StudentAttendanceSheetResponse.model_validate(existing)
        if resolved.academic_session_id is None:
            raise ConflictException("Attendance requires a resolved academic session.")
        enrollments = await AttendanceRepository.list_class_enrollments_for_date(
            db,
            tenant_id,
            class_id=payload.class_id,
            academic_session_id=resolved.academic_session_id,
            attendance_date=target_date,
        )
        if not enrollments:
            raise ConflictException(
                "No active students are enrolled in this class for the attendance date."
            )
        sheet = StudentAttendanceSheet(
            tenant_id=tenant_id,
            class_id=payload.class_id,
            attendance_date=target_date,
            academic_session_id=resolved.academic_session_id,
            academic_term_id=resolved.academic_term_id,
            calendar_id=resolved.calendar_id,
            opened_by_teacher_membership_id=teacher_membership_id,
            notes=payload.notes,
        )
        records = [
            StudentAttendanceRecord(
                tenant_id=tenant_id,
                sheet_id=uuid.uuid4(),
                student_id=enrollment.student_id,
                student_enrollment_id=enrollment.id,
            )
            for enrollment in enrollments
        ]
        await AttendanceRepository.create_student_sheet(db, sheet=sheet, records=records)
        actor_type = (
            AttendanceActorType.TEACHER
            if teacher_membership_id
            else AttendanceActorType.TENANT_ADMIN
        )
        actor_id = teacher_membership_id or acting_admin_id
        await AttendanceRepository.add_audit_log(
            db,
            _actor_audit(
                tenant_id=tenant_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action="student_attendance_sheet.opened",
                entity_type="student_attendance_sheet",
                entity_id=sheet.id,
            ),
        )
        await db.commit()
        return StudentAttendanceSheetResponse.model_validate(sheet)

    @staticmethod
    async def mark_records(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        sheet_id: uuid.UUID,
        payload: StudentAttendanceBulkMarkRequest,
        actor_type: AttendanceActorType,
        actor_id: uuid.UUID,
    ) -> StudentAttendanceSheetResponse:
        sheet = await AttendanceRepository.get_sheet_by_id(db, tenant_id, sheet_id, lock=True)
        if sheet is None:
            raise NotFoundException("Attendance sheet not found.")
        if sheet.status not in {
            StudentAttendanceSheetStatus.DRAFT,
            StudentAttendanceSheetStatus.SUBMITTED,
        }:
            raise ConflictException("Only draft or submitted sheets can be edited.")
        if actor_type == AttendanceActorType.TEACHER:
            allowed_classes = await AttendanceRepository.list_teacher_class_ids(
                db,
                tenant_id,
                teacher_membership_id=actor_id,
                target_date=sheet.attendance_date,
            )
            if sheet.class_id not in allowed_classes:
                raise ForbiddenException(
                    "You are not assigned to edit this class attendance sheet."
                )
        record_by_student = {record.student_id: record for record in sheet.records}
        now = utc_now()
        for item in payload.records:
            record = record_by_student.get(item.student_id)
            if record is None:
                raise BadRequestException(
                    "One or more students do not belong to this attendance sheet."
                )
            record.status = item.status
            record.reason = item.reason
            record.notes = item.notes
            record.marked_at = now
            record.marked_by_actor_type = actor_type
            record.marked_by_actor_id = actor_id
            await AttendanceRepository.save_student_record(db, record)
        await AttendanceRepository.add_audit_log(
            db,
            _actor_audit(
                tenant_id=tenant_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action="student_attendance_records.marked",
                entity_type="student_attendance_sheet",
                entity_id=sheet.id,
                details={"count": len(payload.records)},
            ),
        )
        await db.commit()
        return StudentAttendanceSheetResponse.model_validate(sheet)

    @staticmethod
    async def submit_sheet(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        sheet_id: uuid.UUID,
        payload: StudentAttendanceSheetSubmitRequest,
        teacher_membership_id: uuid.UUID,
    ) -> StudentAttendanceSheetResponse:
        sheet = await AttendanceRepository.get_sheet_by_id(db, tenant_id, sheet_id, lock=True)
        if sheet is None:
            raise NotFoundException("Attendance sheet not found.")
        if sheet.status != StudentAttendanceSheetStatus.DRAFT:
            raise ConflictException("Only draft attendance sheets can be submitted.")
        if any(record.status == StudentAttendanceStatus.UNMARKED for record in sheet.records):
            raise ConflictException("All students must be marked before submission.")
        sheet.status = StudentAttendanceSheetStatus.SUBMITTED
        sheet.submitted_at = utc_now()
        sheet.submitted_by_teacher_membership_id = teacher_membership_id
        sheet.notes = payload.notes or sheet.notes
        await AttendanceRepository.save_student_sheet(db, sheet)
        await db.commit()
        return StudentAttendanceSheetResponse.model_validate(sheet)

    @staticmethod
    async def set_admin_sheet_status(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        sheet_id: uuid.UUID,
        status: StudentAttendanceSheetStatus,
        acting_admin_id: uuid.UUID,
    ) -> StudentAttendanceSheetResponse:
        sheet = await AttendanceRepository.get_sheet_by_id(db, tenant_id, sheet_id, lock=True)
        if sheet is None:
            raise NotFoundException("Attendance sheet not found.")
        now = utc_now()
        if status == StudentAttendanceSheetStatus.APPROVED:
            if sheet.status not in {
                StudentAttendanceSheetStatus.SUBMITTED,
                StudentAttendanceSheetStatus.DRAFT,
            }:
                raise ConflictException("Only draft or submitted sheets can be approved.")
            sheet.approved_at = now
            sheet.approved_by_admin_id = acting_admin_id
        elif status == StudentAttendanceSheetStatus.LOCKED:
            if sheet.status not in {
                StudentAttendanceSheetStatus.APPROVED,
                StudentAttendanceSheetStatus.SUBMITTED,
            }:
                raise ConflictException("Only approved or submitted sheets can be locked.")
            sheet.locked_at = now
            sheet.locked_by_admin_id = acting_admin_id
        elif status == StudentAttendanceSheetStatus.CANCELLED:
            if sheet.status == StudentAttendanceSheetStatus.LOCKED:
                raise ConflictException("Locked sheets cannot be cancelled.")
            sheet.cancelled_at = now
        sheet.status = status
        await AttendanceRepository.save_student_sheet(db, sheet)
        await db.commit()
        return StudentAttendanceSheetResponse.model_validate(sheet)

    @staticmethod
    async def list_sheets(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        class_id: uuid.UUID | None = None,
        status: StudentAttendanceSheetStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> StudentAttendanceSheetListResponse:
        rows, total = await AttendanceRepository.list_student_sheets(
            db,
            tenant_id,
            start_date=start_date,
            end_date=end_date,
            class_id=class_id,
            status=status,
            skip=skip,
            limit=limit,
        )
        return StudentAttendanceSheetListResponse(
            items=[StudentAttendanceSheetResponse.model_validate(row) for row in rows],
            total=total,
        )

    @staticmethod
    async def list_student_records(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> StudentAttendanceRecordListResponse:
        rows, total = await AttendanceRepository.list_student_records_for_student(
            db,
            tenant_id,
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
        return StudentAttendanceRecordListResponse(
            items=[StudentAttendanceRecordResponse.model_validate(row) for row in rows],
            total=total,
        )


class WorkforceAttendanceService:
    @staticmethod
    async def check_in(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_membership_id: uuid.UUID,
        payload: WorkforceCheckInRequest,
    ) -> WorkforceAttendanceResponse:
        target_date = _date_or_tenant_today(
            payload.attendance_date,
            tenant_today=await SchoolCalendarService.tenant_today(db, tenant_id),
        )
        resolved = await SchoolDayPolicyService().require_workforce_attendance_day(
            db, tenant_id=tenant_id, target_date=target_date
        )
        settings = await AttendanceSettingsService.get_or_create_settings(db, tenant_id)
        existing = await AttendanceRepository.get_workforce_record(
            db,
            tenant_id,
            teacher_membership_id=teacher_membership_id,
            attendance_date=target_date,
            lock=True,
        )
        if existing is not None and existing.check_in_at is not None:
            raise ConflictException("You have already checked in for this date.")
        evaluation_id = None
        if settings.require_geofence_for_workforce or payload.location is not None:
            evaluation = await GeofenceService.evaluate(
                db,
                tenant_id=tenant_id,
                actor_type=AttendanceActorType.TEACHER,
                actor_id=teacher_membership_id,
                location=payload.location,
                purpose="workforce_check_in",
                persist=True,
            )
            evaluation_id = evaluation.id
            if (
                settings.require_geofence_for_workforce
                and evaluation.decision != GeofenceDecision.INSIDE.value
            ):
                raise ConflictException(
                    evaluation.reason or "Check-in is outside the allowed geofence."
                )
        record = existing or WorkforceAttendanceRecord(
            tenant_id=tenant_id,
            teacher_membership_id=teacher_membership_id,
            attendance_date=target_date,
            academic_session_id=resolved.academic_session_id,
            academic_term_id=resolved.academic_term_id,
            calendar_id=resolved.calendar_id,
        )
        record.status = WorkforceAttendanceStatus.CHECKED_IN
        record.check_in_at = utc_now()
        record.check_in_geofence_evaluation_id = evaluation_id
        record.check_in_notes = payload.notes
        await AttendanceRepository.save_workforce_record(db, record)
        await db.commit()
        return WorkforceAttendanceResponse.model_validate(record)

    @staticmethod
    async def check_out(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_membership_id: uuid.UUID,
        payload: WorkforceCheckOutRequest,
    ) -> WorkforceAttendanceResponse:
        target_date = _date_or_tenant_today(
            payload.attendance_date,
            tenant_today=await SchoolCalendarService.tenant_today(db, tenant_id),
        )
        await SchoolDayPolicyService().require_workforce_attendance_day(
            db, tenant_id=tenant_id, target_date=target_date
        )
        settings = await AttendanceSettingsService.get_or_create_settings(db, tenant_id)
        record = await AttendanceRepository.get_workforce_record(
            db,
            tenant_id,
            teacher_membership_id=teacher_membership_id,
            attendance_date=target_date,
            lock=True,
        )
        if record is None or record.check_in_at is None:
            raise ConflictException("You must check in before checking out.")
        if record.check_out_at is not None:
            raise ConflictException("You have already checked out for this date.")
        evaluation_id = None
        if settings.require_geofence_for_workforce or payload.location is not None:
            evaluation = await GeofenceService.evaluate(
                db,
                tenant_id=tenant_id,
                actor_type=AttendanceActorType.TEACHER,
                actor_id=teacher_membership_id,
                location=payload.location,
                purpose="workforce_check_out",
                persist=True,
            )
            evaluation_id = evaluation.id
            if (
                settings.require_geofence_for_workforce
                and evaluation.decision != GeofenceDecision.INSIDE.value
            ):
                raise ConflictException(
                    evaluation.reason or "Check-out is outside the allowed geofence."
                )
        record.status = WorkforceAttendanceStatus.CHECKED_OUT
        record.check_out_at = utc_now()
        record.check_out_geofence_evaluation_id = evaluation_id
        record.check_out_notes = payload.notes
        await AttendanceRepository.save_workforce_record(db, record)
        await db.commit()
        return WorkforceAttendanceResponse.model_validate(record)

    @staticmethod
    async def list_records(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_membership_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> WorkforceAttendanceListResponse:
        rows, total = await AttendanceRepository.list_workforce_records(
            db,
            tenant_id,
            teacher_membership_id=teacher_membership_id,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
        return WorkforceAttendanceListResponse(
            items=[WorkforceAttendanceResponse.model_validate(row) for row in rows],
            total=total,
        )


class AttendanceAdminService:
    @staticmethod
    async def create_temporary_assignment(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: TemporaryAttendanceAssignmentCreate,
        acting_admin_id: uuid.UUID,
    ) -> TemporaryAttendanceAssignmentResponse:
        if await AttendanceRepository.get_class(db, tenant_id, payload.class_id) is None:
            raise NotFoundException("Class not found.")
        if (
            await AttendanceRepository.get_teacher_membership(
                db, tenant_id, payload.teacher_membership_id
            )
            is None
        ):
            raise NotFoundException("Teacher membership not found.")
        assignment = TemporaryAttendanceAssignment(
            tenant_id=tenant_id,
            class_id=payload.class_id,
            teacher_membership_id=payload.teacher_membership_id,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            assigned_by_admin_id=acting_admin_id,
            reason=payload.reason,
        )
        await AttendanceRepository.save_temporary_assignment(db, assignment)
        await db.commit()
        return TemporaryAttendanceAssignmentResponse.model_validate(assignment)

    @staticmethod
    async def create_correction(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        payload: AttendanceCorrectionCreate,
        actor_type: AttendanceActorType,
        actor_id: uuid.UUID,
    ) -> AttendanceCorrectionResponse:
        correction = AttendanceCorrection(
            tenant_id=tenant_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            requested_by_actor_type=actor_type,
            requested_by_actor_id=actor_id,
            reason=payload.reason,
            requested_state=payload.requested_state,
        )
        await AttendanceRepository.create_correction(db, correction)
        await db.commit()
        return AttendanceCorrectionResponse.model_validate(correction)

    @staticmethod
    async def review_correction(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        correction_id: uuid.UUID,
        payload: AttendanceCorrectionReview,
        acting_admin_id: uuid.UUID,
    ) -> AttendanceCorrectionResponse:
        correction = await AttendanceRepository.get_correction(
            db, tenant_id, correction_id, lock=True
        )
        if correction is None:
            raise NotFoundException("Correction not found.")
        if correction.status != AttendanceCorrectionStatus.PENDING:
            raise ConflictException("Only pending corrections can be reviewed.")
        correction.status = (
            AttendanceCorrectionStatus.APPROVED
            if payload.approved
            else AttendanceCorrectionStatus.REJECTED
        )
        correction.reviewed_by_admin_id = acting_admin_id
        correction.reviewed_at = utc_now()
        correction.admin_note = payload.admin_note
        if payload.approved:
            correction.applied_state = correction.requested_state
            await AttendanceAdminService._apply_correction(
                db,
                tenant_id=tenant_id,
                correction=correction,
                acting_admin_id=acting_admin_id,
            )
        await AttendanceRepository.create_correction(db, correction)
        await db.commit()
        return AttendanceCorrectionResponse.model_validate(correction)

    @staticmethod
    async def _apply_correction(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        correction: AttendanceCorrection,
        acting_admin_id: uuid.UUID,
    ) -> None:
        data = correction.requested_state
        now = utc_now()
        if correction.target_type == AttendanceCorrectionTarget.STUDENT_RECORD:
            record = await AttendanceRepository.get_student_record_by_id(
                db,
                tenant_id,
                correction.target_id,
                lock=True,
            )
            if record is None:
                raise NotFoundException("Student attendance record not found.")
            correction.previous_state = {
                "status": record.status.value,
                "reason": record.reason,
                "notes": record.notes,
            }
            if "status" in data:
                record.status = StudentAttendanceStatus(data["status"])
            record.reason = data.get("reason", record.reason)
            record.notes = data.get("notes", record.notes)
            record.marked_at = now
            record.marked_by_actor_type = AttendanceActorType.TENANT_ADMIN
            record.marked_by_actor_id = acting_admin_id
            await AttendanceRepository.save_student_record(db, record)
            return
        if correction.target_type == AttendanceCorrectionTarget.WORKFORCE_RECORD:
            record = await AttendanceRepository.get_workforce_record_by_id(
                db,
                tenant_id,
                correction.target_id,
                lock=True,
            )
            if record is None:
                raise NotFoundException("Workforce attendance record not found.")
            correction.previous_state = {
                "status": record.status.value,
                "check_in_at": record.check_in_at,
                "check_out_at": record.check_out_at,
            }
            if "status" in data:
                record.status = WorkforceAttendanceStatus(data["status"])
            if "check_in_at" in data:
                record.check_in_at = (
                    datetime.fromisoformat(data["check_in_at"]) if data["check_in_at"] else None
                )
            if "check_out_at" in data:
                record.check_out_at = (
                    datetime.fromisoformat(data["check_out_at"]) if data["check_out_at"] else None
                )
            record.corrected_by_admin_id = acting_admin_id
            record.corrected_at = now
            await AttendanceRepository.save_workforce_record(db, record)

    @staticmethod
    async def list_corrections(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        status: AttendanceCorrectionStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> AttendanceCorrectionListResponse:
        rows, total = await AttendanceRepository.list_corrections(
            db, tenant_id, status=status, skip=skip, limit=limit
        )
        return AttendanceCorrectionListResponse(
            items=[AttendanceCorrectionResponse.model_validate(row) for row in rows],
            total=total,
        )


class AttendanceAnalyticsService:
    @staticmethod
    async def analytics(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> AttendanceAnalyticsResponse:
        if end_date < start_date:
            raise BadRequestException("end_date must be on or after start_date.")
        student_totals = await AttendanceRepository.count_student_records_by_status(
            db, tenant_id, start_date=start_date, end_date=end_date
        )
        workforce_totals = await AttendanceRepository.count_workforce_records_by_status(
            db, tenant_id, start_date=start_date, end_date=end_date
        )
        student_marked = sum(
            count
            for status, count in student_totals.items()
            if status != StudentAttendanceStatus.UNMARKED.value
        )
        student_positive = student_totals.get(
            StudentAttendanceStatus.PRESENT.value, 0
        ) + student_totals.get(StudentAttendanceStatus.LATE.value, 0)
        workforce_positive = workforce_totals.get(
            WorkforceAttendanceStatus.CHECKED_IN.value, 0
        ) + workforce_totals.get(WorkforceAttendanceStatus.CHECKED_OUT.value, 0)
        workforce_total = sum(workforce_totals.values())
        return AttendanceAnalyticsResponse(
            start_date=start_date,
            end_date=end_date,
            student_totals=student_totals,
            workforce_totals=workforce_totals,
            student_attendance_rate=(
                None if student_marked == 0 else round(student_positive / student_marked, 4)
            ),
            workforce_check_in_rate=(
                None if workforce_total == 0 else round(workforce_positive / workforce_total, 4)
            ),
        )

    @staticmethod
    async def readiness(
        db: AsyncSession, *, tenant_id: uuid.UUID, start_date: date, end_date: date
    ) -> AttendanceReadinessResponse:
        sheets, _ = await AttendanceRepository.list_student_sheets(
            db, tenant_id, start_date=start_date, end_date=end_date, limit=500
        )
        blockers: list[str] = []
        warnings: list[str] = []
        unsubmitted = [
            sheet
            for sheet in sheets
            if sheet.status
            in {
                StudentAttendanceSheetStatus.DRAFT,
                StudentAttendanceSheetStatus.CANCELLED,
            }
        ]
        unmarked = sum(
            1
            for sheet in sheets
            for record in sheet.records
            if record.status == StudentAttendanceStatus.UNMARKED
        )
        if unsubmitted:
            blockers.append("One or more student attendance sheets are still draft or cancelled.")
        if unmarked:
            blockers.append("One or more student attendance records are unmarked.")
        if not sheets:
            warnings.append("No student attendance sheets exist in the selected date range.")
        return AttendanceReadinessResponse(
            ready=not blockers,
            blockers=blockers,
            warnings=warnings,
            counts={
                "sheets": len(sheets),
                "unsubmitted_sheets": len(unsubmitted),
                "unmarked_records": unmarked,
            },
        )
