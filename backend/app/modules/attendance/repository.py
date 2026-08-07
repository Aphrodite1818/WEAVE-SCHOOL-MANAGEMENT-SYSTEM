"""Persistence helpers for attendance workflows."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.attendance.attendance_enums import (
    AttendanceCorrectionStatus,
    SchoolGeofenceStatus,
    StudentAttendanceSheetStatus,
    TemporaryAssignmentStatus,
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
from app.modules.classes.models import ClassRoom
from app.modules.students.models import AcademicStatus, Student, StudentEnrollment
from app.modules.teachers.models import TeacherMembership, TeacherMembershipStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AttendanceRepository:
    @staticmethod
    async def _save(db: AsyncSession, entity):
        db.add(entity)
        await db.flush()
        await db.refresh(entity)
        return entity

    @staticmethod
    async def get_settings(
        db: AsyncSession, tenant_id: uuid.UUID
    ) -> AttendanceSettings | None:
        return (
            await db.execute(
                select(AttendanceSettings).where(
                    AttendanceSettings.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def save_settings(
        db: AsyncSession, settings: AttendanceSettings
    ) -> AttendanceSettings:
        return await AttendanceRepository._save(db, settings)

    @staticmethod
    async def get_class(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> ClassRoom | None:
        return (
            await db.execute(
                select(ClassRoom).where(
                    ClassRoom.tenant_id == tenant_id, ClassRoom.id == class_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_class_enrollments_for_date(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        class_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        attendance_date: date,
    ) -> list[StudentEnrollment]:
        return list(
            (
                await db.execute(
                    select(StudentEnrollment)
                    .join(Student, Student.id == StudentEnrollment.student_id)
                    .where(
                        StudentEnrollment.tenant_id == tenant_id,
                        StudentEnrollment.class_id == class_id,
                        StudentEnrollment.academic_session_id == academic_session_id,
                        StudentEnrollment.started_on <= attendance_date,
                        or_(
                            StudentEnrollment.ended_on.is_(None),
                            StudentEnrollment.ended_on >= attendance_date,
                        ),
                        Student.tenant_id == tenant_id,
                        Student.status == AcademicStatus.ACTIVE,
                        Student.is_active.is_(True),
                        Student.is_archived.is_(False),
                    )
                    .order_by(
                        Student.last_name.asc().nulls_last(),
                        Student.first_name.asc().nulls_last(),
                        Student.admission_number.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def get_sheet_by_class_date(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        class_id: uuid.UUID,
        attendance_date: date,
        lock: bool = False,
    ) -> StudentAttendanceSheet | None:
        query = (
            select(StudentAttendanceSheet)
            .where(
                StudentAttendanceSheet.tenant_id == tenant_id,
                StudentAttendanceSheet.class_id == class_id,
                StudentAttendanceSheet.attendance_date == attendance_date,
            )
            .options(selectinload(StudentAttendanceSheet.records))
        )
        if lock:
            query = query.with_for_update(of=StudentAttendanceSheet)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_sheet_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        sheet_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> StudentAttendanceSheet | None:
        query = (
            select(StudentAttendanceSheet)
            .where(
                StudentAttendanceSheet.tenant_id == tenant_id,
                StudentAttendanceSheet.id == sheet_id,
            )
            .options(selectinload(StudentAttendanceSheet.records))
        )
        if lock:
            query = query.with_for_update(of=StudentAttendanceSheet)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def create_student_sheet(
        db: AsyncSession,
        *,
        sheet: StudentAttendanceSheet,
        records: list[StudentAttendanceRecord],
    ) -> StudentAttendanceSheet:
        db.add(sheet)
        await db.flush()
        for record in records:
            record.sheet_id = sheet.id
        db.add_all(records)
        await db.flush()
        await db.refresh(sheet, attribute_names=["records"])
        return sheet

    @staticmethod
    async def save_student_sheet(
        db: AsyncSession, sheet: StudentAttendanceSheet
    ) -> StudentAttendanceSheet:
        return await AttendanceRepository._save(db, sheet)

    @staticmethod
    async def save_student_record(
        db: AsyncSession, record: StudentAttendanceRecord
    ) -> StudentAttendanceRecord:
        return await AttendanceRepository._save(db, record)

    @staticmethod
    async def get_student_record_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        record_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> StudentAttendanceRecord | None:
        query = select(StudentAttendanceRecord).where(
            StudentAttendanceRecord.tenant_id == tenant_id,
            StudentAttendanceRecord.id == record_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_student_sheets(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        class_id: uuid.UUID | None = None,
        status: StudentAttendanceSheetStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[StudentAttendanceSheet], int]:
        filters = [StudentAttendanceSheet.tenant_id == tenant_id]
        if start_date is not None:
            filters.append(StudentAttendanceSheet.attendance_date >= start_date)
        if end_date is not None:
            filters.append(StudentAttendanceSheet.attendance_date <= end_date)
        if class_id is not None:
            filters.append(StudentAttendanceSheet.class_id == class_id)
        if status is not None:
            filters.append(StudentAttendanceSheet.status == status)
        total = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentAttendanceSheet)
                    .where(*filters)
                )
            ).scalar_one()
        )
        rows = list(
            (
                await db.execute(
                    select(StudentAttendanceSheet)
                    .where(*filters)
                    .options(selectinload(StudentAttendanceSheet.records))
                    .order_by(StudentAttendanceSheet.attendance_date.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return rows, total

    @staticmethod
    async def list_student_records_for_student(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        student_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[StudentAttendanceRecord], int]:
        filters = [
            StudentAttendanceRecord.tenant_id == tenant_id,
            StudentAttendanceRecord.student_id == student_id,
            StudentAttendanceSheet.tenant_id == tenant_id,
        ]
        if start_date is not None:
            filters.append(StudentAttendanceSheet.attendance_date >= start_date)
        if end_date is not None:
            filters.append(StudentAttendanceSheet.attendance_date <= end_date)
        total = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentAttendanceRecord)
                    .join(
                        StudentAttendanceSheet,
                        StudentAttendanceSheet.id == StudentAttendanceRecord.sheet_id,
                    )
                    .where(*filters)
                )
            ).scalar_one()
        )
        rows = list(
            (
                await db.execute(
                    select(StudentAttendanceRecord)
                    .join(
                        StudentAttendanceSheet,
                        StudentAttendanceSheet.id == StudentAttendanceRecord.sheet_id,
                    )
                    .where(*filters)
                    .order_by(StudentAttendanceSheet.attendance_date.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return rows, total

    @staticmethod
    async def list_teacher_class_ids(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        teacher_membership_id: uuid.UUID,
        target_date: date,
    ) -> set[uuid.UUID]:
        direct = (
            (
                await db.execute(
                    select(ClassRoom.id).where(
                        ClassRoom.tenant_id == tenant_id,
                        ClassRoom.teacher_membership_id == teacher_membership_id,
                        ClassRoom.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        temporary = (
            (
                await db.execute(
                    select(TemporaryAttendanceAssignment.class_id).where(
                        TemporaryAttendanceAssignment.tenant_id == tenant_id,
                        TemporaryAttendanceAssignment.teacher_membership_id
                        == teacher_membership_id,
                        TemporaryAttendanceAssignment.status
                        == TemporaryAssignmentStatus.ACTIVE,
                        TemporaryAttendanceAssignment.starts_on <= target_date,
                        TemporaryAttendanceAssignment.ends_on >= target_date,
                    )
                )
            )
            .scalars()
            .all()
        )
        return {item for item in [*direct, *temporary]}

    @staticmethod
    async def get_teacher_membership(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        teacher_membership_id: uuid.UUID,
    ) -> TeacherMembership | None:
        return (
            await db.execute(
                select(TeacherMembership).where(
                    TeacherMembership.tenant_id == tenant_id,
                    TeacherMembership.id == teacher_membership_id,
                    TeacherMembership.status == TeacherMembershipStatus.ACTIVE,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_active_geofence(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        geofence_id: uuid.UUID | None = None,
    ) -> SchoolGeofence | None:
        filters = [
            SchoolGeofence.tenant_id == tenant_id,
            SchoolGeofence.status == SchoolGeofenceStatus.ACTIVE,
        ]
        if geofence_id is not None:
            filters.append(SchoolGeofence.id == geofence_id)
        order_by = (SchoolGeofence.is_primary.desc(), SchoolGeofence.created_at.asc())
        return (
            await db.execute(
                select(SchoolGeofence).where(*filters).order_by(*order_by).limit(1)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_geofences(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        include_archived: bool = False,
    ) -> tuple[list[SchoolGeofence], int]:
        filters = [SchoolGeofence.tenant_id == tenant_id]
        if not include_archived:
            filters.append(SchoolGeofence.status != SchoolGeofenceStatus.ARCHIVED)
        total = int(
            (
                await db.execute(
                    select(func.count()).select_from(SchoolGeofence).where(*filters)
                )
            ).scalar_one()
        )
        rows = list(
            (
                await db.execute(
                    select(SchoolGeofence)
                    .where(*filters)
                    .order_by(
                        SchoolGeofence.is_primary.desc(), SchoolGeofence.name.asc()
                    )
                )
            )
            .scalars()
            .all()
        )
        return rows, total

    @staticmethod
    async def get_geofence(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        geofence_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> SchoolGeofence | None:
        query = select(SchoolGeofence).where(
            SchoolGeofence.tenant_id == tenant_id, SchoolGeofence.id == geofence_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def clear_primary_geofence(db: AsyncSession, tenant_id: uuid.UUID) -> None:
        rows = (
            (
                await db.execute(
                    select(SchoolGeofence).where(
                        SchoolGeofence.tenant_id == tenant_id,
                        SchoolGeofence.is_primary.is_(True),
                        SchoolGeofence.status == SchoolGeofenceStatus.ACTIVE,
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            row.is_primary = False
            db.add(row)
        await db.flush()

    @staticmethod
    async def save_geofence(
        db: AsyncSession, geofence: SchoolGeofence
    ) -> SchoolGeofence:
        return await AttendanceRepository._save(db, geofence)

    @staticmethod
    async def save_geofence_evaluation(
        db: AsyncSession, evaluation: GeofenceEvaluation
    ) -> GeofenceEvaluation:
        return await AttendanceRepository._save(db, evaluation)

    @staticmethod
    async def get_workforce_record(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        teacher_membership_id: uuid.UUID,
        attendance_date: date,
        lock: bool = False,
    ) -> WorkforceAttendanceRecord | None:
        query = select(WorkforceAttendanceRecord).where(
            WorkforceAttendanceRecord.tenant_id == tenant_id,
            WorkforceAttendanceRecord.teacher_membership_id == teacher_membership_id,
            WorkforceAttendanceRecord.attendance_date == attendance_date,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def save_workforce_record(
        db: AsyncSession, record: WorkforceAttendanceRecord
    ) -> WorkforceAttendanceRecord:
        return await AttendanceRepository._save(db, record)

    @staticmethod
    async def get_workforce_record_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        record_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> WorkforceAttendanceRecord | None:
        query = select(WorkforceAttendanceRecord).where(
            WorkforceAttendanceRecord.tenant_id == tenant_id,
            WorkforceAttendanceRecord.id == record_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_workforce_records(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        teacher_membership_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[WorkforceAttendanceRecord], int]:
        filters = [WorkforceAttendanceRecord.tenant_id == tenant_id]
        if start_date is not None:
            filters.append(WorkforceAttendanceRecord.attendance_date >= start_date)
        if end_date is not None:
            filters.append(WorkforceAttendanceRecord.attendance_date <= end_date)
        if teacher_membership_id is not None:
            filters.append(
                WorkforceAttendanceRecord.teacher_membership_id == teacher_membership_id
            )
        total = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(WorkforceAttendanceRecord)
                    .where(*filters)
                )
            ).scalar_one()
        )
        rows = list(
            (
                await db.execute(
                    select(WorkforceAttendanceRecord)
                    .where(*filters)
                    .order_by(WorkforceAttendanceRecord.attendance_date.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return rows, total

    @staticmethod
    async def save_temporary_assignment(
        db: AsyncSession, assignment: TemporaryAttendanceAssignment
    ) -> TemporaryAttendanceAssignment:
        return await AttendanceRepository._save(db, assignment)

    @staticmethod
    async def create_correction(
        db: AsyncSession, correction: AttendanceCorrection
    ) -> AttendanceCorrection:
        return await AttendanceRepository._save(db, correction)

    @staticmethod
    async def get_correction(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        correction_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> AttendanceCorrection | None:
        query = select(AttendanceCorrection).where(
            AttendanceCorrection.tenant_id == tenant_id,
            AttendanceCorrection.id == correction_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_corrections(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        status: AttendanceCorrectionStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AttendanceCorrection], int]:
        filters = [AttendanceCorrection.tenant_id == tenant_id]
        if status is not None:
            filters.append(AttendanceCorrection.status == status)
        total = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(AttendanceCorrection)
                    .where(*filters)
                )
            ).scalar_one()
        )
        rows = list(
            (
                await db.execute(
                    select(AttendanceCorrection)
                    .where(*filters)
                    .order_by(AttendanceCorrection.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return rows, total

    @staticmethod
    async def save_notification(
        db: AsyncSession, notification: AttendanceNotification
    ) -> AttendanceNotification:
        return await AttendanceRepository._save(db, notification)

    @staticmethod
    async def add_audit_log(
        db: AsyncSession, audit: AttendanceAuditLog
    ) -> AttendanceAuditLog:
        return await AttendanceRepository._save(db, audit)

    @staticmethod
    async def purge_expired_location_evidence(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> dict[str, int]:
        current = now or utc_now()
        filters = [
            GeofenceEvaluation.raw_location_expires_at.is_not(None),
            GeofenceEvaluation.raw_location_expires_at <= current,
            GeofenceEvaluation.latitude_raw.is_not(None),
        ]
        if tenant_id is not None:
            filters.append(GeofenceEvaluation.tenant_id == tenant_id)
        raw_result = await db.execute(
            update(GeofenceEvaluation)
            .where(*filters)
            .values(latitude_raw=None, longitude_raw=None, device_context=None)
            .execution_options(synchronize_session=False)
        )

        evidence_filters = [
            GeofenceEvaluation.evidence_expires_at.is_not(None),
            GeofenceEvaluation.evidence_expires_at <= current,
        ]
        if tenant_id is not None:
            evidence_filters.append(GeofenceEvaluation.tenant_id == tenant_id)
        evidence_result = await db.execute(
            update(GeofenceEvaluation)
            .where(*evidence_filters)
            .values(
                reason="Expired attendance geofence evidence retained without raw location."
            )
            .execution_options(synchronize_session=False)
        )
        await db.flush()
        return {
            "raw_locations_purged": int(raw_result.rowcount or 0),
            "evidence_rows_touched": int(evidence_result.rowcount or 0),
        }

    @staticmethod
    async def count_student_records_by_status(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        start_date: date,
        end_date: date,
    ) -> dict[str, int]:
        rows = (
            await db.execute(
                select(StudentAttendanceRecord.status, func.count())
                .join(
                    StudentAttendanceSheet,
                    StudentAttendanceSheet.id == StudentAttendanceRecord.sheet_id,
                )
                .where(
                    StudentAttendanceRecord.tenant_id == tenant_id,
                    StudentAttendanceSheet.tenant_id == tenant_id,
                    StudentAttendanceSheet.attendance_date >= start_date,
                    StudentAttendanceSheet.attendance_date <= end_date,
                )
                .group_by(StudentAttendanceRecord.status)
            )
        ).all()
        return {status.value: int(count) for status, count in rows}

    @staticmethod
    async def count_workforce_records_by_status(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        start_date: date,
        end_date: date,
    ) -> dict[str, int]:
        rows = (
            await db.execute(
                select(WorkforceAttendanceRecord.status, func.count())
                .where(
                    WorkforceAttendanceRecord.tenant_id == tenant_id,
                    WorkforceAttendanceRecord.attendance_date >= start_date,
                    WorkforceAttendanceRecord.attendance_date <= end_date,
                )
                .group_by(WorkforceAttendanceRecord.status)
            )
        ).all()
        return {status.value: int(count) for status, count in rows}
