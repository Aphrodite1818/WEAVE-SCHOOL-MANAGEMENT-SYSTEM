# ====================================== #
#       auth_identity/models.py          #
# ====================================== #

"""Database model for actor login identity lookup."""

import uuid
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Enum as SqlEnum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin, UUIDMixin


class IdentifierType(str, PyEnum):
    """Supported login identifier types."""

    EMAIL = "email"
    ADMISSION_NUMBER = "admission_number"


class ActorType(str, PyEnum):
    """Supported authenticatable actor types."""

    TENANT_ADMIN = "tenant_admin"
    TEACHER = "teacher"
    STAFF = "staff"
    PARENT = "parent"
    STUDENT = "student"


class AuthIdentity(UUIDMixin, TimestampMixin, Base):
    """Lookup table that maps a login identifier to its owning actor."""

    __tablename__ = "auth_identities"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenants.id"),
        nullable=True,
        index=True,
        doc=(
            "Tenant scope for tenant-bound actors. NULL for global accounts "
            "such as parent_accounts and teacher_accounts."
        ),
    )

    identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Unique login identifier such as email or admission number.",
    )

    identifier_type: Mapped[IdentifierType] = mapped_column(
        SqlEnum(
            IdentifierType,
            name="identifier_type",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    actor_type: Mapped[ActorType] = mapped_column(
        SqlEnum(
            ActorType,
            name="actor_type",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    __table_args__ = (
        UniqueConstraint(
            "identifier_type",
            "identifier",
            name="uq_auth_identities_identifier",
        ),
        UniqueConstraint(
            "actor_type",
            "actor_id",
            name="uq_auth_identities_actor",
        ),
        Index(
            "ix_auth_identities_active_identifier",
            "identifier_type",
            "identifier",
            "is_active",
        ),
    )
