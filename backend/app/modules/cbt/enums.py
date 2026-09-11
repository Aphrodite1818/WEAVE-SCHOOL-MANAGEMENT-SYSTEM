# ====================================== #
#             cbt/enums.py               #
# ====================================== #

"""Enums used by the CBT integration domain."""

from enum import Enum as PyEnum


class CBTServerStatus(str, PyEnum):
    """Lifecycle state of a paired CBT server."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class CBTResultIngestionStatus(str, PyEnum):
    """Lifecycle state of a CBT result-ingestion batch."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_REJECTIONS = "completed_with_rejections"
    REJECTED = "rejected"
    FAILED = "failed"


class CBTResultIngestionOutcome(str, PyEnum):
    """Processing outcome for one student score inside an ingestion batch."""

    APPLIED = "applied"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"
