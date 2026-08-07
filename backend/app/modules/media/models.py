# ==========================#
#      media.models        #
# ==========================#
"""Database models for the media module.

This file will hold the persistent representation of uploaded media and
any related metadata needed by the application.
"""

from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String,
    DateTime,
    Enum as SQLEnum,
    Integer,
    Text,
    ForeignKey,
    Index,
    Boolean,
    BigInteger,
)
from datetime import datetime
from enum import Enum as PyEnum

import uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


class MediaOwnerType(str, PyEnum):
    """Entity type that owns the uploaded media asset"""

    TENANT = "tenant"
    STUDENT = "student"
    TEACHER = "teacher"
    TENANT_ADMIN = "tenant_admin"


class MediaPurpose(str, PyEnum):
    """Business purpose of a media asset"""

    SCHOOL_LOGO = "school_logo"
    STUDENT_PASSPORT = "student_passport"
    TEACHER_PASSPORT = "teacher_passport"
    TENANT_ADMIN_PASSPORT = "tenant_admin_passport"


class MediaVisibility(str, PyEnum):
    """visibility level for stored media"""

    PUBLIC = "public"
    PRIVATE = "private"


class MediaStatus(str, PyEnum):
    """Lifecycle status of a media asset"""

    ACTIVE = "active"
    REPLACED = "replaced"
    DELETED = "deleted"


class MediaStorageProvider(str, PyEnum):
    """Storage provider used for the physical file object."""

    LOCAL = "local"
    R2 = "r2"


class MediaUploadedByActorType(str, PyEnum):
    """Actor type that uploaded the media asset."""

    TENANT_ADMIN = "tenant_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"
    SUPERADMIN = "superadmin"


class MediaAsset(BaseModel):
    """Metadata record for a file stored outside the database

    The binary file itself lives in storage , this table stores ownership , tenant isolation,
    object key , URL , size MIME type , and lifecycle state
    """

    __tablename__ = "media_assets"

    owner_type: Mapped[MediaOwnerType] = mapped_column(
        SQLEnum(
            MediaOwnerType,
            name="media_owner_type",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        index=True,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment=(
            "Polymorphic owner ID. References tenant/student/teacher/"
            "tenant_admin depending on owner_type."
        ),
    )

    purpose: Mapped[MediaPurpose] = mapped_column(
        SQLEnum(
            MediaPurpose,
            name="media_purpose",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        index=True,
    )

    visibility: Mapped[MediaVisibility] = mapped_column(
        SQLEnum(
            MediaVisibility,
            name="media_visibility",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=MediaVisibility.PRIVATE,
        server_default=MediaVisibility.PRIVATE.value,
    )

    status: Mapped[MediaStatus] = mapped_column(
        SQLEnum(
            MediaStatus,
            name="media_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=MediaStatus.ACTIVE,
        server_default=MediaStatus.ACTIVE.value,
        index=True,
    )

    storage_provider: Mapped[MediaStorageProvider] = mapped_column(
        SQLEnum(
            MediaStorageProvider,
            name="media_storage_provider",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=MediaStorageProvider.LOCAL,
        server_default=MediaStorageProvider.LOCAL.value,
    )

    bucket: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Storage bucket/container name.",
    )

    object_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Provider object key/path, for example tenants/{tenant_id}/students/{id}/passport/{media_id}.webp.",
    )

    public_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Stable public or CDN URL when the object is public.",
    )

    cdn_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Cached CDN URL for fast public delivery when available.",
    )

    signed_url_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Expiry time when public_url stores a temporary signed URL.",
    )

    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="Validated MIME type, for example image/jpeg or image/webp.",
    )

    extension: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Normalized file extension without a leading dot.",
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA-256 checksum of the uploaded file bytes.",
    )

    etag: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Object storage ETag returned by the backend when available.",
    )

    cache_control: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Cache-Control policy applied to the stored object.",
    )

    width_px: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    height_px: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Provider-specific metadata, image processing metadata, or audit details.",
    )

    uploaded_by_actor_type: Mapped[MediaUploadedByActorType | None] = mapped_column(
        SQLEnum(
            MediaUploadedByActorType,
            name="media_uploaded_by_actor_type",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )

    uploaded_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Marks the latest active media for a given owner/purpose.",
    )

    replaced_by_media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_media_assets_tenant_owner_purpose_current",
            "tenant_id",
            "owner_type",
            "owner_id",
            "purpose",
            "is_current",
        ),
        Index(
            "ix_media_assets_tenant_purpose_status",
            "tenant_id",
            "purpose",
            "status",
        ),
        Index(
            "ix_media_assets_tenant_object_key",
            "tenant_id",
            "object_key",
        ),
        Index(
            "ix_media_assets_tenant_visibility_status",
            "tenant_id",
            "visibility",
            "status",
        ),
    )

    def __repr__(self) -> str:
        """Return a concise debug representation."""

        return (
            f"<MediaAsset id={self.id} tenant_id={self.tenant_id} "
            f"owner_type={self.owner_type!r} purpose={self.purpose!r} "
            f"status={self.status!r}>"
        )

    @property
    def is_active(self) -> bool:
        """Return whether the media asset is active and not deleted."""

        return self.status == MediaStatus.ACTIVE and self.deleted_at is None
