"""Enums for attendance and geofence workflows."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import Any


def enum_values(enum_cls: type[PyEnum]) -> list[Any]:
    return [item.value for item in enum_cls]


class AttendanceActorType(str, PyEnum):
    TENANT_ADMIN = "tenant_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"
    SYSTEM = "system"


class AttendanceSettingsStatus(str, PyEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class SchoolGeofenceStatus(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class GeofenceDecision(str, PyEnum):
    INSIDE = "inside"
    OUTSIDE = "outside"
    INACCURATE = "inaccurate"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class StudentAttendanceSheetStatus(str, PyEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    LOCKED = "locked"
    CANCELLED = "cancelled"


class StudentAttendanceStatus(str, PyEnum):
    UNMARKED = "unmarked"
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class WorkforceAttendanceStatus(str, PyEnum):
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    ABSENT = "absent"
    EXCUSED = "excused"
    CORRECTED = "corrected"


class TemporaryAssignmentStatus(str, PyEnum):
    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"


class AttendanceCorrectionTarget(str, PyEnum):
    STUDENT_RECORD = "student_record"
    WORKFORCE_RECORD = "workforce_record"


class AttendanceCorrectionStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AttendanceNotificationChannel(str, PyEnum):
    EMAIL = "email"
    IN_APP = "in_app"


class AttendanceNotificationStatus(str, PyEnum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"
