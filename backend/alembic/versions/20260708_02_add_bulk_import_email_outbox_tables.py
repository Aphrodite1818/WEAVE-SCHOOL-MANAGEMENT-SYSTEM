"""add bulk import and email outbox tables

Revision ID: 20260708_add_bulk_import_email_outbox
Revises: 20260708_dev_reset_schema
Create Date: 2026-07-08 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260708_add_bulk_import"
down_revision: str | Sequence[str] | None = "20260708_dev_reset_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_ENUMS_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typname = 'import_resource_type'
    ) THEN
        CREATE TYPE public.import_resource_type AS ENUM (
            'students',
            'teachers',
            'parents',
            'classes',
            'subjects',
            'class_subjects',
            'teacher_subjects',
            'assessment_records'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typname = 'import_file_type'
    ) THEN
        CREATE TYPE public.import_file_type AS ENUM ('csv', 'xlsx');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typname = 'import_job_status'
    ) THEN
        CREATE TYPE public.import_job_status AS ENUM (
            'pending',
            'processing',
            'completed',
            'partially_completed',
            'failed',
            'cancelled'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typname = 'import_notification_channel'
    ) THEN
        CREATE TYPE public.import_notification_channel AS ENUM ('in_app', 'email');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typname = 'import_notification_status'
    ) THEN
        CREATE TYPE public.import_notification_status AS ENUM ('pending', 'sent', 'failed');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typname = 'email_outbox_status'
    ) THEN
        CREATE TYPE public.email_outbox_status AS ENUM (
            'pending',
            'processing',
            'sent',
            'failed',
            'cancelled'
        );
    END IF;
END $$;
"""


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS public.import_jobs (
    id UUID NOT NULL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES public.tenants (id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

    resource_type public.import_resource_type NOT NULL,
    file_type public.import_file_type NOT NULL,
    status public.import_job_status NOT NULL DEFAULT 'pending',

    created_by_admin_id UUID NULL REFERENCES public.tenant_admins (id),
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NULL,
    source_file_path TEXT NULL,
    result_file_path TEXT NULL,
    file_size_bytes INTEGER NULL,

    total_rows INTEGER NOT NULL DEFAULT 0,
    processed_rows INTEGER NOT NULL DEFAULT 0,
    successful_rows INTEGER NOT NULL DEFAULT 0,
    failed_rows INTEGER NOT NULL DEFAULT 0,
    skipped_rows INTEGER NOT NULL DEFAULT 0,

    error_message TEXT NULL,
    started_at TIMESTAMP WITH TIME ZONE NULL,
    completed_at TIMESTAMP WITH TIME ZONE NULL,
    metadata_json JSONB NULL
);

CREATE TABLE IF NOT EXISTS public.import_row_errors (
    id UUID NOT NULL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES public.tenants (id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

    import_job_id UUID NOT NULL REFERENCES public.import_jobs (id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    field_name VARCHAR(120) NULL,
    error_code VARCHAR(120) NULL,
    error_message TEXT NOT NULL,
    raw_row JSONB NULL,
    normalized_row JSONB NULL
);

CREATE TABLE IF NOT EXISTS public.import_notifications (
    id UUID NOT NULL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES public.tenants (id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

    import_job_id UUID NOT NULL REFERENCES public.import_jobs (id) ON DELETE CASCADE,
    recipient_admin_id UUID NULL REFERENCES public.tenant_admins (id),
    channel public.import_notification_channel NOT NULL DEFAULT 'in_app',
    status public.import_notification_status NOT NULL DEFAULT 'pending',
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT false,
    sent_at TIMESTAMP WITH TIME ZONE NULL,
    read_at TIMESTAMP WITH TIME ZONE NULL,
    failure_reason TEXT NULL
);

CREATE TABLE IF NOT EXISTS public.email_outbox (
    id UUID NOT NULL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES public.tenants (id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

    recipient_email VARCHAR(255) NOT NULL,
    recipient_name VARCHAR(255) NULL,
    subject VARCHAR(255) NOT NULL,
    template_name VARCHAR(120) NOT NULL,
    template_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    status public.email_outbox_status NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 4,
    next_retry_at TIMESTAMP WITH TIME ZONE NULL,
    processing_started_at TIMESTAMP WITH TIME ZONE NULL,
    sent_at TIMESTAMP WITH TIME ZONE NULL,
    failure_reason TEXT NULL,
    metadata_json JSONB NULL
);
"""


CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS ix_import_jobs_tenant_status
    ON public.import_jobs (tenant_id, status);
CREATE INDEX IF NOT EXISTS ix_import_jobs_tenant_resource_type
    ON public.import_jobs (tenant_id, resource_type);
CREATE INDEX IF NOT EXISTS ix_import_jobs_tenant_created_by
    ON public.import_jobs (tenant_id, created_by_admin_id);
CREATE INDEX IF NOT EXISTS ix_import_jobs_tenant_created_at
    ON public.import_jobs (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_import_jobs_status_created_at
    ON public.import_jobs (status, created_at);

CREATE INDEX IF NOT EXISTS ix_import_row_errors_tenant_job
    ON public.import_row_errors (tenant_id, import_job_id);
CREATE INDEX IF NOT EXISTS ix_import_row_errors_tenant_job_row
    ON public.import_row_errors (tenant_id, import_job_id, row_number);
CREATE INDEX IF NOT EXISTS ix_import_row_errors_tenant_error_code
    ON public.import_row_errors (tenant_id, error_code);

CREATE INDEX IF NOT EXISTS ix_import_notifications_tenant_job
    ON public.import_notifications (tenant_id, import_job_id);
CREATE INDEX IF NOT EXISTS ix_import_notifications_tenant_recipient
    ON public.import_notifications (tenant_id, recipient_admin_id);
CREATE INDEX IF NOT EXISTS ix_import_notifications_tenant_status
    ON public.import_notifications (tenant_id, status);
CREATE INDEX IF NOT EXISTS ix_import_notifications_tenant_read
    ON public.import_notifications (tenant_id, is_read);

CREATE INDEX IF NOT EXISTS ix_email_outbox_tenant_status
    ON public.email_outbox (tenant_id, status);
CREATE INDEX IF NOT EXISTS ix_email_outbox_tenant_retry
    ON public.email_outbox (tenant_id, status, next_retry_at);
CREATE INDEX IF NOT EXISTS ix_email_outbox_recipient_status
    ON public.email_outbox (recipient_email, status);
CREATE INDEX IF NOT EXISTS ix_email_outbox_template_status
    ON public.email_outbox (template_name, status);
"""


DROP_INDEXES_SQL = """
DROP INDEX IF EXISTS public.ix_email_outbox_template_status;
DROP INDEX IF EXISTS public.ix_email_outbox_recipient_status;
DROP INDEX IF EXISTS public.ix_email_outbox_tenant_retry;
DROP INDEX IF EXISTS public.ix_email_outbox_tenant_status;

DROP INDEX IF EXISTS public.ix_import_notifications_tenant_read;
DROP INDEX IF EXISTS public.ix_import_notifications_tenant_status;
DROP INDEX IF EXISTS public.ix_import_notifications_tenant_recipient;
DROP INDEX IF EXISTS public.ix_import_notifications_tenant_job;

DROP INDEX IF EXISTS public.ix_import_row_errors_tenant_error_code;
DROP INDEX IF EXISTS public.ix_import_row_errors_tenant_job_row;
DROP INDEX IF EXISTS public.ix_import_row_errors_tenant_job;

DROP INDEX IF EXISTS public.ix_import_jobs_status_created_at;
DROP INDEX IF EXISTS public.ix_import_jobs_tenant_created_at;
DROP INDEX IF EXISTS public.ix_import_jobs_tenant_created_by;
DROP INDEX IF EXISTS public.ix_import_jobs_tenant_resource_type;
DROP INDEX IF EXISTS public.ix_import_jobs_tenant_status;
"""


DROP_TABLES_SQL = """
DROP TABLE IF EXISTS public.email_outbox;
DROP TABLE IF EXISTS public.import_notifications;
DROP TABLE IF EXISTS public.import_row_errors;
DROP TABLE IF EXISTS public.import_jobs;
"""


DROP_ENUMS_SQL = """
DROP TYPE IF EXISTS public.email_outbox_status;
DROP TYPE IF EXISTS public.import_notification_status;
DROP TYPE IF EXISTS public.import_notification_channel;
DROP TYPE IF EXISTS public.import_job_status;
DROP TYPE IF EXISTS public.import_file_type;
DROP TYPE IF EXISTS public.import_resource_type;
"""


def execute_sql_block(sql_block: str) -> None:
    """Execute semicolon-separated SQL statements one at a time.

    asyncpg rejects multiple SQL commands inside one prepared statement, so each
    CREATE TABLE / CREATE INDEX / DROP statement must be executed separately.
    """

    for statement in sql_block.split(";"):
        statement = statement.strip()

        if statement:
            op.execute(statement)


def upgrade() -> None:
    """Create bulk import and email outbox database objects."""

    op.execute(CREATE_ENUMS_SQL)
    execute_sql_block(CREATE_TABLES_SQL)
    execute_sql_block(CREATE_INDEXES_SQL)


def downgrade() -> None:
    """Drop bulk import and email outbox database objects."""

    execute_sql_block(DROP_INDEXES_SQL)
    execute_sql_block(DROP_TABLES_SQL)
    execute_sql_block(DROP_ENUMS_SQL)
