"""Database model for canonical login identity lookup."""

from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin, UUIDMixin


class IdentifierType(str, PyEnum):
    EMAIL = "email"
    ADMISSION_NUMBER = "admission_number"


class ActorType(str, PyEnum):
    """Canonical identity owners.

    Parent and teacher email identities belong to global accounts. Tenant
    memberships are selected after account authentication and therefore never
    own an AuthIdentity row.
    """

    TENANT_ADMIN = "tenant_admin"
    TEACHER_ACCOUNT = "teacher_account"
    STAFF = "staff"
    PARENT_ACCOUNT = "parent_account"
    STUDENT = "student"

    # Transitional enum members retained only so pre-refactor rows can be read
    # until the corrective migration rewrites them.
    TEACHER = "teacher"
    PARENT = "parent"


class AuthIdentity(UUIDMixin, TimestampMixin, Base):
    """Maps one normalized login identifier to its canonical account owner."""

    __tablename__ = "auth_identities"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
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
        CheckConstraint(
            """
            (
                actor_type IN ('teacher_account', 'parent_account')
                AND tenant_id IS NULL
            )
            OR
            (
                actor_type IN ('tenant_admin', 'staff', 'student')
                AND tenant_id IS NOT NULL
            )
            OR actor_type IN ('teacher', 'parent')
            """,
            name="ck_auth_identity_actor_scope",
        ),
        Index(
            "ix_auth_identities_active_identifier",
            "identifier_type",
            "identifier",
            "is_active",
        ),
    )
