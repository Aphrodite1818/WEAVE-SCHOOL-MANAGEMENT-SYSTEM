"""add import staged rows

Revision ID: 20260708_add_import_staged_rows
Revises: 20260708_add_bulk_import_email_outbox
Create Date: 2026-07-08 03:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "add_import_staged_rows"
down_revision: str | Sequence[str] | None = "20260708_add_bulk_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS public.import_staged_rows (
    id UUID NOT NULL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    import_job_id UUID NOT NULL REFERENCES public.import_jobs(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    raw_row JSONB NOT NULL DEFAULT '{}'::jsonb,
    normalized_row JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_import_staged_rows_job_row UNIQUE (import_job_id, row_number)
);
"""

CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS ix_import_staged_rows_tenant_job
ON public.import_staged_rows (tenant_id, import_job_id);

CREATE INDEX IF NOT EXISTS ix_import_staged_rows_job_row
ON public.import_staged_rows (import_job_id, row_number);
"""

DROP_INDEXES_SQL = """
DROP INDEX IF EXISTS public.ix_import_staged_rows_job_row;
DROP INDEX IF EXISTS public.ix_import_staged_rows_tenant_job;
"""

DROP_TABLES_SQL = """
DROP TABLE IF EXISTS public.import_staged_rows;
"""


def execute_sql_block(sql_block: str) -> None:
    """Execute semicolon-separated SQL statements one at a time.

    asyncpg rejects multiple SQL commands inside one prepared statement.
    """

    for statement in sql_block.split(";"):
        statement = statement.strip()

        if statement:
            op.execute(statement)


def upgrade() -> None:
    execute_sql_block(CREATE_TABLES_SQL)
    execute_sql_block(CREATE_INDEXES_SQL)


def downgrade() -> None:
    execute_sql_block(DROP_INDEXES_SQL)
    execute_sql_block(DROP_TABLES_SQL)
