# ====================================#
# backend.app.modules.cbt.sync.enums.py
# ====================================#


from enum import Enum as PyEnum


class CBTSyncOperation(str, PyEnum):
    """various sync operationis Weave cloud can pass to cbt for processing"""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class CBTSyncEntityType(str, PyEnum):
    """various entities operations can be performed on"""

    ACADEMIC_LEVEL = "academic_level"
    DEPARTMENT = "department"
    ARM_LABEL = "arm_label"
    CLASS = "class"

    ACADEMIC_SESSION = "academic_session"
    ACADEMIC_TERM = "academic_term"

    SUBJECT = "subject"
    LEVEL_SUBJECT = "level_subject"
    SUBJECT_OFFERING = "subject_offering"

    ASSESSMENT_SCHEME = "assessment_scheme"
    ASSESSMENT_COMPONENT = "assessment_component"

    TEACHER = "teacher"
    TEACHER_ASSIGNMENT = "teacher_assignment"

    STUDENT_ENROLLMENT = "student_enrollment"
