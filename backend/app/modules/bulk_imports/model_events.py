"""SQLAlchemy safeguards for sensitive bulk-import metadata."""

from __future__ import annotations

from sqlalchemy import event

from app.modules.bulk_imports.models import ImportJob
from app.modules.bulk_imports.sensitive_results import protect_import_metadata


@event.listens_for(ImportJob, "before_insert")
@event.listens_for(ImportJob, "before_update")
def protect_import_job_metadata(mapper, connection, target: ImportJob) -> None:
    """Encrypt setup-code values before an import job is persisted."""

    _ = mapper, connection
    target.metadata_json = protect_import_metadata(target.metadata_json)
