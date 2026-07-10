# ====================================== #
#       tenant_admins/models.py          #
# ====================================== #

"""Tenant admin domain models."""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


class TenantAdminStatus(str, PyEnum):
    """Tenant admin account status."""

    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class TenantAdmin(BaseModel):
    """Tenant administrator account for managing a school tenant."""

    __tablename__ = "tenant_admins"

    email: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    passport_photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    account_status: Mapped[TenantAdminStatus] = mapped_column(
        SqlEnum(
            TenantAdminStatus,
            name="tenant_admin_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=TenantAdminStatus.PENDING,
        server_default=TenantAdminStatus.PENDING.value,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_tenant_admins_tenant_email",
            "tenant_id",
            "email",
        ),
    )
