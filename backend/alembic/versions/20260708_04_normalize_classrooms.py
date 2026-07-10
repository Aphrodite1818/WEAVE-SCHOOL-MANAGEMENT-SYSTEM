"""normalize classrooms

Revision ID: 20260708_normalize_classrooms
Revises: 20260708_add_import_staged_rows
Create Date: 2026-07-08 04:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260708_normalize_classrooms"
down_revision: str | Sequence[str] | None = "20260708_add_import_staged_rows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_NORMALIZE_CLASS_NAME_FUNCTION_SQL = r"""
CREATE OR REPLACE FUNCTION public._learnly_normalize_class_name(input_text TEXT)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    cleaned TEXT;
    compact TEXT;
BEGIN
    IF input_text IS NULL OR btrim(input_text) = '' THEN
        RETURN NULL;
    END IF;

    cleaned := regexp_replace(btrim(input_text), '[\s_\-]+', ' ', 'g');
    compact := upper(regexp_replace(cleaned, '[^A-Za-z0-9]+', '', 'g'));

    IF compact ~ '^JSS[0-9]+$' THEN
        RETURN compact;
    END IF;

    IF compact ~ '^JUNIORSECONDARY[0-9]+$' THEN
        RETURN regexp_replace(compact, '^JUNIORSECONDARY', 'JSS');
    END IF;

    IF compact ~ '^SSS[0-9]+$' THEN
        RETURN regexp_replace(compact, '^SSS', 'SS');
    END IF;

    IF compact ~ '^SS[0-9]+$' THEN
        RETURN compact;
    END IF;

    IF compact ~ '^SENIORSECONDARY[0-9]+$' THEN
        RETURN regexp_replace(compact, '^SENIORSECONDARY', 'SS');
    END IF;

    IF compact ~ '^PRY[0-9]+$' THEN
        RETURN regexp_replace(compact, '^PRY', 'PRIMARY');
    END IF;

    RETURN compact;
END;
$$;
"""

CREATE_NORMALIZE_CLASS_ARM_FUNCTION_SQL = r"""
CREATE OR REPLACE FUNCTION public._learnly_normalize_class_arm(input_text TEXT)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    compact TEXT;
BEGIN
    IF input_text IS NULL OR btrim(input_text) = '' THEN
        RETURN '';
    END IF;

    compact := upper(regexp_replace(btrim(input_text), '\s+', '', 'g'));

    IF compact IN ('-', 'NOARM', 'NO_ARM', 'NO ARM', 'NONE', 'N/A', 'NA') THEN
        RETURN '';
    END IF;

    RETURN compact;
END;
$$;
"""

UPGRADE_STATEMENTS = [
    """
    ALTER TABLE public.classes
    ADD COLUMN IF NOT EXISTS normalized_name VARCHAR(120)
    """,
    """
    ALTER TABLE public.classes
    ADD COLUMN IF NOT EXISTS normalized_arm VARCHAR(40)
    """,
    """
    UPDATE public.classes
    SET
        name = public._learnly_normalize_class_name(name),
        arm = NULLIF(public._learnly_normalize_class_arm(arm), ''),
        normalized_name = public._learnly_normalize_class_name(name),
        normalized_arm = public._learnly_normalize_class_arm(arm)
    WHERE normalized_name IS NULL OR normalized_arm IS NULL
    """,
    """
    DO $$
    DECLARE
        duplicate_count INTEGER;
    BEGIN
        SELECT COUNT(*)
        INTO duplicate_count
        FROM (
            SELECT tenant_id, normalized_name, normalized_arm, COUNT(*) AS row_count
            FROM public.classes
            GROUP BY tenant_id, normalized_name, normalized_arm
            HAVING COUNT(*) > 1
        ) duplicate_groups;

        IF duplicate_count > 0 THEN
            RAISE EXCEPTION 'Cannot normalize classrooms because duplicate normalized class name/arm groups exist. Merge or delete duplicate class records first.';
        END IF;
    END;
    $$
    """,
    """
    ALTER TABLE public.classes
    ALTER COLUMN normalized_name SET NOT NULL
    """,
    """
    ALTER TABLE public.classes
    ALTER COLUMN normalized_arm SET DEFAULT ''
    """,
    """
    ALTER TABLE public.classes
    ALTER COLUMN normalized_arm SET NOT NULL
    """,
    """
    ALTER TABLE public.classes
    ALTER COLUMN arm DROP NOT NULL
    """,
    """
    ALTER TABLE public.classes
    DROP CONSTRAINT IF EXISTS uq_classes_tenant_name_arm
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'uq_classes_tenant_normalized_name_arm'
        ) THEN
            ALTER TABLE public.classes
            ADD CONSTRAINT uq_classes_tenant_normalized_name_arm
            UNIQUE (tenant_id, normalized_name, normalized_arm);
        END IF;
    END;
    $$
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_classes_tenant_normalized_lookup
    ON public.classes (tenant_id, normalized_name, normalized_arm)
    """,
]

DOWNGRADE_STATEMENTS = [
    "DROP INDEX IF EXISTS public.ix_classes_tenant_normalized_lookup",
    "ALTER TABLE public.classes DROP CONSTRAINT IF EXISTS uq_classes_tenant_normalized_name_arm",
    "UPDATE public.classes SET arm = '' WHERE arm IS NULL",
    "ALTER TABLE public.classes ALTER COLUMN arm SET NOT NULL",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'uq_classes_tenant_name_arm'
        ) THEN
            ALTER TABLE public.classes
            ADD CONSTRAINT uq_classes_tenant_name_arm
            UNIQUE (tenant_id, name, arm);
        END IF;
    END;
    $$
    """,
    "ALTER TABLE public.classes DROP COLUMN IF EXISTS normalized_arm",
    "ALTER TABLE public.classes DROP COLUMN IF EXISTS normalized_name",
]

DROP_HELPERS_STATEMENTS = [
    "DROP FUNCTION IF EXISTS public._learnly_normalize_class_arm(TEXT)",
    "DROP FUNCTION IF EXISTS public._learnly_normalize_class_name(TEXT)",
]


def execute_statements(statements: list[str]) -> None:
    """Execute SQL statements one at a time for asyncpg compatibility."""

    for statement in statements:
        op.execute(statement.strip())


def create_helper_functions() -> None:
    """Create temporary migration helper functions."""

    op.execute(CREATE_NORMALIZE_CLASS_NAME_FUNCTION_SQL)
    op.execute(CREATE_NORMALIZE_CLASS_ARM_FUNCTION_SQL)


def drop_helper_functions() -> None:
    """Drop temporary migration helper functions."""

    execute_statements(DROP_HELPERS_STATEMENTS)


def upgrade() -> None:
    create_helper_functions()
    execute_statements(UPGRADE_STATEMENTS)
    drop_helper_functions()


def downgrade() -> None:
    create_helper_functions()
    execute_statements(DOWNGRADE_STATEMENTS)
    drop_helper_functions()
