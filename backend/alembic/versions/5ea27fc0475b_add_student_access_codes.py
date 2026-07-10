"""add student access codes

Revision ID: 5ea27fc0475b
Revises: 20260708_dev_reset_schema
Create Date: 2026-07-07 02:13:41.743446

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "5ea27fc0475b"
down_revision: Union[str, Sequence[str], None] = "20260708_dev_reset_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PUBLIC_SCHEMA = "public"
ACCESS_CODE_PURPOSE_ENUM = "student_access_code_purpose"


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name, schema=PUBLIC_SCHEMA)


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(table_name, schema=PUBLIC_SCHEMA):
        return False

    return any(
        column["name"] == column_name
        for column in inspector.get_columns(table_name, schema=PUBLIC_SCHEMA)
    )


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(table_name, schema=PUBLIC_SCHEMA):
        return False

    return any(
        index["name"] == index_name
        for index in inspector.get_indexes(table_name, schema=PUBLIC_SCHEMA)
    )


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Existing students table changes.
    if _table_exists("students"):
        if not _column_exists("students", "state_of_origin"):
            op.add_column(
                "students",
                sa.Column("state_of_origin", sa.String(length=100), nullable=True),
                schema=PUBLIC_SCHEMA,
            )

        # New flow allows newly-created students to have no real password yet.
        op.alter_column(
            "students",
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=True,
            schema=PUBLIC_SCHEMA,
        )

    # 2. Enum for student access code purpose.
    op.execute(
        f"""
        DO $$
        BEGIN
            CREATE TYPE {PUBLIC_SCHEMA}.{ACCESS_CODE_PURPOSE_ENUM}
            AS ENUM ('initial_setup', 'password_reset');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )

    student_access_code_purpose = postgresql.ENUM(
        "initial_setup",
        "password_reset",
        name=ACCESS_CODE_PURPOSE_ENUM,
        schema=PUBLIC_SCHEMA,
        create_type=False,
    )

    # 3. student_access_codes table.
    if not _table_exists("student_access_codes"):
        op.create_table(
            "student_access_codes",
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column(
                "code_digest",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column(
                "purpose",
                student_access_code_purpose,
                nullable=False,
            ),
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "is_used",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
            sa.Column(
                "used_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "created_by_admin_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["created_by_admin_id"],
                [f"{PUBLIC_SCHEMA}.tenant_admins.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["student_id"],
                [f"{PUBLIC_SCHEMA}.students.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"],
                [f"{PUBLIC_SCHEMA}.tenants.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("id"),
            schema=PUBLIC_SCHEMA,
        )

    # 4. Indexes. Keep these separate so the migration is safe if table was
    # already created by the dev reset migration.
    indexes = [
        (
            "ix_student_access_codes_tenant_student",
            ["tenant_id", "student_id"],
        ),
        (
            "ix_student_access_codes_tenant_code_digest",
            ["tenant_id", "code_digest"],
        ),
        (
            "ix_student_access_codes_tenant_student_used",
            ["tenant_id", "student_id", "is_used"],
        ),
        (
            "ix_student_access_codes_expires_at",
            ["expires_at"],
        ),
        (
            "ix_student_access_codes_is_used",
            ["is_used"],
        ),
    ]

    for index_name, columns in indexes:
        if not _index_exists("student_access_codes", index_name):
            op.create_index(
                index_name,
                "student_access_codes",
                columns,
                schema=PUBLIC_SCHEMA,
            )


def downgrade() -> None:
    """Downgrade schema."""

    if _table_exists("student_access_codes"):
        op.drop_index(
            "ix_student_access_codes_is_used",
            table_name="student_access_codes",
            schema=PUBLIC_SCHEMA,
        )
        op.drop_index(
            "ix_student_access_codes_expires_at",
            table_name="student_access_codes",
            schema=PUBLIC_SCHEMA,
        )
        op.drop_index(
            "ix_student_access_codes_tenant_student_used",
            table_name="student_access_codes",
            schema=PUBLIC_SCHEMA,
        )
        op.drop_index(
            "ix_student_access_codes_tenant_code_digest",
            table_name="student_access_codes",
            schema=PUBLIC_SCHEMA,
        )
        op.drop_index(
            "ix_student_access_codes_tenant_student",
            table_name="student_access_codes",
            schema=PUBLIC_SCHEMA,
        )
        op.drop_table("student_access_codes", schema=PUBLIC_SCHEMA)

    op.execute(
        f'DROP TYPE IF EXISTS {PUBLIC_SCHEMA}.{ACCESS_CODE_PURPOSE_ENUM}'
    )

    if _table_exists("students"):
        if _column_exists("students", "state_of_origin"):
            op.drop_column("students", "state_of_origin", schema=PUBLIC_SCHEMA)

        # Warning: this can fail if any rows still have password_hash = NULL.
        op.alter_column(
            "students",
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=False,
            schema=PUBLIC_SCHEMA,
        )