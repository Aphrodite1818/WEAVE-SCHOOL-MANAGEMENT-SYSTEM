"""Create global teacher accounts and tenant memberships.

Revision ID: 7b2f6c9d4e10
Revises: 0f4c2d7a9b11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7b2f6c9d4e10"
down_revision = "0f4c2d7a9b11"
branch_labels = None
depends_on = None

PUBLIC_SCHEMA = "public"


def upgrade() -> None:
    bind = op.get_bind()

    postgresql.ENUM(
        "pending", "active", "locked", "inactive",
        name="teacher_account_status_v2",
        schema=PUBLIC_SCHEMA,
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "active", "suspended", "inactive",
        name="teacher_membership_status",
        schema=PUBLIC_SCHEMA,
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "pending", "accepted", "expired", "revoked",
        name="teacher_invitation_status",
        schema=PUBLIC_SCHEMA,
    ).create(bind, checkfirst=True)

    op.rename_table("teachers", "legacy_teachers", schema=PUBLIC_SCHEMA)

    op.create_table(
        "teacher_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(300), nullable=False),
        sa.Column("password_hash", sa.String(300), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("qualification", sa.String(100), nullable=True),
        sa.Column("specialization", sa.String(150), nullable=True),
        sa.Column("passport_photo_url", sa.String(500), nullable=True),
        sa.Column(
            "account_status",
            postgresql.ENUM(
                "pending", "active", "locked", "inactive",
                name="teacher_account_status_v2",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_teacher_accounts_email"),
        schema=PUBLIC_SCHEMA,
    )
    op.create_index("ix_teacher_accounts_email", "teacher_accounts", ["email"], schema=PUBLIC_SCHEMA)
    op.create_index("ix_teacher_accounts_status_active", "teacher_accounts", ["account_status", "is_active"], schema=PUBLIC_SCHEMA)

    op.create_table(
        "teacher_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("staff_id", sa.String(50), nullable=True),
        sa.Column("job_title", sa.String(100), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("employment_type", sa.String(50), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "suspended", "inactive",
                name="teacher_membership_status",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(500), nullable=True),
        sa.Column("receive_email_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("receive_push_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["teacher_account_id"], ["public.teacher_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_account_id", "tenant_id", name="uq_teacher_memberships_account_tenant"),
        sa.UniqueConstraint("tenant_id", "staff_id", name="uq_teacher_memberships_tenant_staff_id"),
        sa.CheckConstraint(
            "(status IN ('active', 'suspended') AND ended_at IS NULL) OR (status = 'inactive' AND ended_at IS NOT NULL)",
            name="ck_teacher_membership_status_end_consistency",
        ),
        schema=PUBLIC_SCHEMA,
    )
    op.create_index("ix_teacher_memberships_tenant_status", "teacher_memberships", ["tenant_id", "status"], schema=PUBLIC_SCHEMA)
    op.create_index("ix_teacher_memberships_account_status", "teacher_memberships", ["teacher_account_id", "status"], schema=PUBLIC_SCHEMA)

    op.create_table(
        "teacher_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invited_email", sa.String(300), nullable=False),
        sa.Column("token_digest", sa.String(255), nullable=False),
        sa.Column("staff_id", sa.String(50), nullable=True),
        sa.Column("job_title", sa.String(100), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("employment_type", sa.String(50), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "accepted", "expired", "revoked",
                name="teacher_invitation_status",
                schema=PUBLIC_SCHEMA,
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_by_teacher_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_by_teacher_account_id"], ["public.teacher_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest", name="uq_teacher_invitations_token_digest"),
        sa.CheckConstraint(
            "(status = 'accepted' AND accepted_at IS NOT NULL AND accepted_by_teacher_account_id IS NOT NULL) OR status <> 'accepted'",
            name="ck_teacher_invitation_acceptance_consistency",
        ),
        sa.CheckConstraint(
            "(status = 'revoked' AND revoked_at IS NOT NULL) OR status <> 'revoked'",
            name="ck_teacher_invitation_revocation_consistency",
        ),
        schema=PUBLIC_SCHEMA,
    )
    op.create_index("ix_teacher_invitations_tenant_email_status", "teacher_invitations", ["tenant_id", "invited_email", "status"], schema=PUBLIC_SCHEMA)
    op.create_index(
        "uq_teacher_invitations_pending_email",
        "teacher_invitations",
        ["tenant_id", "invited_email"],
        unique=True,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "teacher_membership_subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["teacher_membership_id"], ["public.teacher_memberships.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["public.subjects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "teacher_membership_id", "subject_id", name="uq_teacher_membership_subjects_tenant_membership_subject"),
        schema=PUBLIC_SCHEMA,
    )

    op.execute(
        """
        INSERT INTO public.teacher_accounts (
            id, email, password_hash, first_name, last_name, qualification,
            specialization, passport_photo_url, account_status, is_verified,
            is_active, last_login_at, created_at, updated_at
        )
        SELECT DISTINCT ON (lower(trim(email)))
            gen_random_uuid(), lower(trim(email)), password_hash, first_name,
            last_name, qualification, specialization, passport_photo_url,
            CASE WHEN is_active THEN 'active' ELSE 'inactive' END::public.teacher_account_status_v2,
            is_verified, is_active, last_login_at, created_at, updated_at
        FROM public.legacy_teachers
        ORDER BY lower(trim(email)), created_at ASC, id ASC
        """
    )

    op.execute(
        """
        INSERT INTO public.teacher_memberships (
            id, tenant_id, teacher_account_id, staff_id, status, joined_at,
            ended_at, end_reason, created_at, updated_at
        )
        SELECT
            legacy.id,
            legacy.tenant_id,
            account.id,
            legacy.staff_id,
            CASE WHEN legacy.is_active THEN 'active' ELSE 'inactive' END::public.teacher_membership_status,
            legacy.created_at,
            CASE WHEN legacy.is_active THEN NULL ELSE legacy.updated_at END,
            CASE WHEN legacy.is_active THEN NULL ELSE 'Migrated inactive teacher' END,
            legacy.created_at,
            legacy.updated_at
        FROM public.legacy_teachers legacy
        JOIN public.teacher_accounts account
          ON account.email = lower(trim(legacy.email))
        """
    )

    op.execute(
        """
        INSERT INTO public.teacher_membership_subjects (
            id, tenant_id, teacher_membership_id, subject_id, is_active, created_at, updated_at
        )
        SELECT id, tenant_id, teacher_id, subject_id, true, created_at, updated_at
        FROM public.teacher_subjects
        """
    )

    op.drop_table("teacher_subjects", schema=PUBLIC_SCHEMA)

    op.drop_constraint("classes_teacher_id_fkey", "classes", schema=PUBLIC_SCHEMA, type_="foreignkey")
    op.alter_column("classes", "teacher_id", new_column_name="teacher_membership_id", schema=PUBLIC_SCHEMA)
    op.create_foreign_key(
        "fk_classes_teacher_membership_id",
        "classes", "teacher_memberships",
        ["teacher_membership_id"], ["id"],
        source_schema=PUBLIC_SCHEMA,
        referent_schema=PUBLIC_SCHEMA,
        ondelete="SET NULL",
    )

    for table_name in ("teacher_assignments", "class_subject_teachers", "student_subject_results"):
        old_constraint = f"{table_name}_teacher_id_fkey"
        op.drop_constraint(old_constraint, table_name, schema=PUBLIC_SCHEMA, type_="foreignkey")
        op.alter_column(table_name, "teacher_id", new_column_name="teacher_membership_id", schema=PUBLIC_SCHEMA)
        op.create_foreign_key(
            f"fk_{table_name}_teacher_membership_id",
            table_name,
            "teacher_memberships",
            ["teacher_membership_id"],
            ["id"],
            source_schema=PUBLIC_SCHEMA,
            referent_schema=PUBLIC_SCHEMA,
            ondelete="RESTRICT",
        )

    op.drop_table("legacy_teachers", schema=PUBLIC_SCHEMA)


def downgrade() -> None:
    raise RuntimeError(
        "Global teacher-account migration is intentionally irreversible. "
        "Restore a pre-migration database backup instead."
    )
