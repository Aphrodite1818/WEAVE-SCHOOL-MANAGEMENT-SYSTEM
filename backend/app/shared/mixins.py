#======================================#
#              mixins.py               #
#======================================#
"""Reusable SQLAlchemy mixins shared across multiple models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    """Return an application-side timezone-aware UTC timestamp.

    Async ORM responses must not depend on implicit database I/O to retrieve
    server-generated timestamp values after a flush. Keeping a database default
    still protects direct SQL inserts, while the Python defaults ensure mapped
    instances already contain serializable values.
    """

    return datetime.now(timezone.utc)


class TimestampMixin:
    """Add created_at and updated_at timestamps to mapped models."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
        nullable=False,
    )


class UUIDMixin:
    """Add a UUID primary key to mapped models."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        unique=True,
    )
