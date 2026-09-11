"""Stable wire-level CBT synchronization enums."""

from enum import Enum as PyEnum


class CBTSyncOperation(str, PyEnum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class CBTSyncEntityType(str, PyEnum):
    ACADEMIC_LEVEL = "academic_level"
    DEPARTMENT = "department"
    ARM_LABEL = "arm_label"
    CLASS = "class"
    CLASS_TERM_DEPARTMENT = "class_term_department"

    ACADEMIC_SESSION = "academic_session"
    ACADEMIC_TERM = "academic_term"

    SUBJECT = "subject"
    CURRICULUM = "curriculum"
    CURRICULUM_SUBJECT = "curriculum_subject"
    CURRICULUM_SUBJECT_DEPARTMENT = "curriculum_subject_department"

    ASSESSMENT_SCHEME = "assessment_scheme"
    ASSESSMENT_COMPONENT = "assessment_component"

    ADMIN = "admin"
    TEACHER = "teacher"
    TEACHER_ASSIGNMENT = "teacher_assignment"

    STUDENT_ENROLLMENT = "student_enrollment"
