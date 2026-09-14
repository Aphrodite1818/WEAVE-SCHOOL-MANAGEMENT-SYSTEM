"""Communication domain enums."""

from __future__ import annotations

from enum import Enum
from typing import Any


def enum_values(enum_cls: type[Enum]) -> list[Any]:
    return [item.value for item in enum_cls]


class CommunicationActorType(str, Enum):
    SUPERADMIN = "superadmin"
    TENANT_ADMIN = "tenant_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


class ConversationType(str, Enum):
    DIRECT = "direct"
    SUPPORT = "support"


class NoticeAudienceType(str, Enum):
    ALL_TENANT_ADMINS = "all_tenant_admins"
    SELECTED_TENANT_ADMINS = "selected_tenant_admins"
    TENANT_ADMINS_OF_TENANTS = "tenant_admins_of_tenants"
    ALL_TEACHERS = "all_teachers"
    SELECTED_TEACHERS = "selected_teachers"
    ALL_STUDENTS = "all_students"
    SELECTED_STUDENTS = "selected_students"
    CLASS_STUDENTS = "class_students"
    ALL_PARENTS = "all_parents"
    SELECTED_PARENTS = "selected_parents"
    CLASS_PARENTS = "class_parents"


class NoticeCategory(str, Enum):
    GENERAL = "general"
    ACADEMIC = "academic"
    ATTENDANCE = "attendance"
    EVENT = "event"
    FINANCE = "finance"
    EMERGENCY = "emergency"
    SYSTEM = "system"


class NoticePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NoticeStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class NotificationSourceType(str, Enum):
    NOTICE = "notice"
    MESSAGE = "message"
    SYSTEM_EVENT = "system_event"
    ATTENDANCE_REMINDER = "attendance_reminder"
    ATTENDANCE_CORRECTION = "attendance_correction"
    BULK_IMPORT = "bulk_import"
    CALENDAR_EVENT = "calendar_event"
    ACADEMIC_LIFECYCLE = "academic_lifecycle"
    SUBSCRIPTION = "subscription"
    ACCOUNT_ALERT = "account_alert"


class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"
