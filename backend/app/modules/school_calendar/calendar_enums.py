"""School calendar enum definitions."""

from __future__ import annotations

from enum import Enum as PyEnum


class SchoolCalendarStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class SchoolCalendarDayType(str, PyEnum):
    INSTRUCTIONAL_DAY = "instructional_day"
    EXAMINATION_DAY = "examination_day"
    WEEKEND = "weekend"
    PUBLIC_HOLIDAY = "public_holiday"
    SCHOOL_HOLIDAY = "school_holiday"
    MID_TERM_BREAK = "mid_term_break"
    STAFF_TRAINING_DAY = "staff_training_day"
    SPECIAL_SCHOOL_DAY = "special_school_day"
    EMERGENCY_CLOSURE = "emergency_closure"


class SchoolCalendarDaySource(str, PyEnum):
    GENERATED = "generated"
    MANUAL = "manual"
    SYSTEM = "system"


class SchoolCalendarEventType(str, PyEnum):
    ACADEMIC = "academic"
    HOLIDAY = "holiday"
    EXAMINATION = "examination"
    MEETING = "meeting"
    ACTIVITY = "activity"
    EMERGENCY = "emergency"
    OTHER = "other"


class SchoolCalendarEventAudience(str, PyEnum):
    ALL = "all"
    TENANT_ADMINS = "tenant_admins"
    TEACHERS = "teachers"
    PARENTS = "parents"
    STUDENTS = "students"


class SchoolCalendarEventStatus(str, PyEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
