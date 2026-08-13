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