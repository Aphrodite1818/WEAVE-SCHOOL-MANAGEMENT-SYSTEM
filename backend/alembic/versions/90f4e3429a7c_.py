"""add media assets and tenant branding

Revision ID: 90f4e3429a7c
Revises: 644a6ebe31fe
Create Date: 2026-07-10 19:08:35.442523
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "90f4e3429a7c"
down_revision: Union[str, Sequence[str], None] = "644a6ebe31fe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PUBLIC_SCHEMA = "public"


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("media_assets", schema=PUBLIC_SCHEMA):
        return

    # -------------------------------------------------------------------------
    # Media assets
    # -------------------------------------------------------------------------

    op.execute("CREATE TYPE public.media_owner_type AS ENUM ('tenant', 'student', 'teacher', 'tenant_admin')")
    op.execute("CREATE TYPE public.media_purpose AS ENUM ('school_logo', 'student_passport', 'teacher_passport', 'tenant_admin_passport')")
    op.execute("CREATE TYPE public.media_visibility AS ENUM ('public', 'private')")
    op.execute("CREATE TYPE public.media_status AS ENUM ('active', 'replaced', 'deleted')")
    op.execute("CREATE TYPE public.media_storage_provider AS ENUM ('local', 'r2')")
    op.execute("CREATE TYPE public.media_uploaded_by_actor_type AS ENUM ('tenant_admin', 'teacher', 'student', 'parent', 'superadmin')")

    op.create_table(
        "media_assets",
        sa.Column(
            "owner_type",
            sa.Enum(
                "tenant",
                "student",
                "teacher",
                "tenant_admin",
                name="media_owner_type",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment=(
                "Polymorphic owner ID. References tenant/student/teacher/"
                "tenant_admin depending on owner_type."
            ),
        ),
        sa.Column(
            "purpose",
            sa.Enum(
                "school_logo",
                "student_passport",
                "teacher_passport",
                "tenant_admin_passport",
                name="media_purpose",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            sa.Enum(
                "public",
                "private",
                name="media_visibility",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            server_default="private",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "replaced",
                "deleted",
                name="media_status",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "storage_provider",
            sa.Enum(
                "local",
                "r2",
                name="media_storage_provider",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            server_default="local",
            nullable=False,
        ),
        sa.Column(
            "bucket",
            sa.String(length=255),
            nullable=False,
            comment="Storage bucket/container name.",
        ),
        sa.Column(
            "object_key",
            sa.Text(),
            nullable=False,
            comment=(
                "Provider object key/path, for example "
                "tenants/{tenant_id}/students/{id}/passport/{media_id}.webp."
            ),
        ),
        sa.Column(
            "public_url",
            sa.Text(),
            nullable=True,
            comment="Stable public or CDN URL when the object is public.",
        ),
        sa.Column(
            "cdn_url",
            sa.Text(),
            nullable=True,
            comment="Cached CDN URL for fast public delivery when available.",
        ),
        sa.Column(
            "signed_url_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Expiry time for the latest generated signed URL.",
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column(
            "content_type",
            sa.String(length=120),
            nullable=False,
            comment="Validated MIME type, for example image/jpeg or image/webp.",
        ),
        sa.Column(
            "extension",
            sa.String(length=20),
            nullable=True,
            comment="Normalized file extension without a leading dot.",
        ),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "checksum_sha256",
            sa.String(length=64),
            nullable=True,
            comment="SHA-256 checksum of the uploaded file bytes.",
        ),
        sa.Column(
            "etag",
            sa.String(length=255),
            nullable=True,
            comment="Object storage ETag returned by the backend when available.",
        ),
        sa.Column(
            "cache_control",
            sa.String(length=255),
            nullable=True,
            comment="Cache-Control policy applied to the stored object.",
        ),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Provider-specific metadata, image processing metadata, or audit details.",
        ),
        sa.Column(
            "uploaded_by_actor_type",
            sa.Enum(
                "tenant_admin",
                "teacher",
                "student",
                "parent",
                "superadmin",
                name="media_uploaded_by_actor_type",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("uploaded_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default="true",
            nullable=False,
            comment="Marks the latest active media for a given owner/purpose.",
        ),
        sa.Column("replaced_by_media_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            [f"{PUBLIC_SCHEMA}.tenants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_media_asset_id"],
            [f"{PUBLIC_SCHEMA}.media_assets.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=PUBLIC_SCHEMA,
    )

    op.create_index(
        "ix_media_assets_tenant_object_key",
        "media_assets",
        ["tenant_id", "object_key"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_media_assets_tenant_owner_purpose_current",
        "media_assets",
        ["tenant_id", "owner_type", "owner_id", "purpose", "is_current"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_media_assets_tenant_purpose_status",
        "media_assets",
        ["tenant_id", "purpose", "status"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_media_assets_tenant_visibility_status",
        "media_assets",
        ["tenant_id", "visibility", "status"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_public_media_assets_checksum_sha256",
        "media_assets",
        ["checksum_sha256"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_public_media_assets_owner_id",
        "media_assets",
        ["owner_id"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_public_media_assets_owner_type",
        "media_assets",
        ["owner_type"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_public_media_assets_purpose",
        "media_assets",
        ["purpose"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_public_media_assets_status",
        "media_assets",
        ["status"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )

    # -------------------------------------------------------------------------
    # Tenant branding
    # -------------------------------------------------------------------------

    op.create_table(
        "tenant_branding",
        sa.Column("brand_name", sa.String(length=255), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=False),
        sa.Column("accent_color", sa.String(length=7), nullable=False),
        sa.Column("sidebar_color", sa.String(length=7), nullable=False),
        sa.Column(
            "theme_mode",
            sa.Enum(
                "light",
                "dark",
                name="tenant_branding_theme_mode",
                schema=PUBLIC_SCHEMA,
            ),
            server_default="light",
            nullable=False,
        ),
        sa.Column(
            "tokens",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "theme_version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("updated_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            [f"{PUBLIC_SCHEMA}.tenants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_admin_id"],
            [f"{PUBLIC_SCHEMA}.tenant_admins.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_branding_tenant_id"),
        schema=PUBLIC_SCHEMA,
    )

    op.create_index(
        "ix_tenant_branding_tenant_enabled",
        "tenant_branding",
        ["tenant_id", "is_enabled"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )

    # -------------------------------------------------------------------------
    # Profile media fields
    # -------------------------------------------------------------------------

    op.add_column(
        "teachers",
        sa.Column("passport_photo_url", sa.String(length=500), nullable=True),
        schema=PUBLIC_SCHEMA,
    )

    op.add_column(
        "tenant_admins",
        sa.Column("passport_photo_url", sa.String(length=500), nullable=True),
        schema=PUBLIC_SCHEMA,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # -------------------------------------------------------------------------
    # Profile media fields
    # -------------------------------------------------------------------------

    op.drop_column("tenant_admins", "passport_photo_url", schema=PUBLIC_SCHEMA)
    op.drop_column("teachers", "passport_photo_url", schema=PUBLIC_SCHEMA)

    # -------------------------------------------------------------------------
    # Tenant branding
    # -------------------------------------------------------------------------

    op.drop_index(
        "ix_tenant_branding_tenant_enabled",
        table_name="tenant_branding",
        schema=PUBLIC_SCHEMA,
    )

    op.drop_table("tenant_branding", schema=PUBLIC_SCHEMA)

    op.execute("DROP TYPE IF EXISTS public.tenant_branding_theme_mode")

    # -------------------------------------------------------------------------
    # Media assets
    # -------------------------------------------------------------------------

    op.drop_index(
        "ix_public_media_assets_status",
        table_name="media_assets",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_public_media_assets_purpose",
        table_name="media_assets",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_public_media_assets_owner_type",
        table_name="media_assets",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_public_media_assets_owner_id",
        table_name="media_assets",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_public_media_assets_checksum_sha256",
        table_name="media_assets",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_media_assets_tenant_visibility_status",
        table_name="media_assets",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_media_assets_tenant_purpose_status",
        table_name="media_assets",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_media_assets_tenant_owner_purpose_current",
        table_name="media_assets",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_media_assets_tenant_object_key",
        table_name="media_assets",
        schema=PUBLIC_SCHEMA,
    )

    op.drop_table("media_assets", schema=PUBLIC_SCHEMA)

    op.execute("DROP TYPE IF EXISTS public.media_uploaded_by_actor_type")
    op.execute("DROP TYPE IF EXISTS public.media_storage_provider")
    op.execute("DROP TYPE IF EXISTS public.media_status")
    op.execute("DROP TYPE IF EXISTS public.media_visibility")
    op.execute("DROP TYPE IF EXISTS public.media_purpose")
    op.execute("DROP TYPE IF EXISTS public.media_owner_type")