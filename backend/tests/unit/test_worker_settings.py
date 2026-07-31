from __future__ import annotations

from app.core.queue.arq import (
    ATTENDANCE_QUEUE_NAME,
    BULK_IMPORT_QUEUE_NAME,
    EMAIL_QUEUE_NAME,
    SESSION_PROGRESSION_QUEUE_NAME,
)
from app.core.queue.attendance_worker import WorkerSettings as AttendanceWorkerSettings
from app.core.queue.bulk_import_worker import WorkerSettings as BulkImportWorkerSettings
from app.core.queue.email_worker import WorkerSettings as EmailWorkerSettings
from app.core.queue.progression_worker import WorkerSettings as ProgressionWorkerSettings


def _function_names(worker_settings) -> set[str]:
    return {function.__name__ for function in worker_settings.functions}


def test_email_worker_registration_imports_cleanly() -> None:
    assert EmailWorkerSettings.queue_name == EMAIL_QUEUE_NAME
    assert "process_email_outbox_batch" in _function_names(EmailWorkerSettings)


def test_bulk_import_worker_registration_imports_cleanly() -> None:
    assert BulkImportWorkerSettings.queue_name == BULK_IMPORT_QUEUE_NAME
    assert "process_bulk_import_job" in _function_names(BulkImportWorkerSettings)


def test_progression_worker_registration_imports_cleanly() -> None:
    assert ProgressionWorkerSettings.queue_name == SESSION_PROGRESSION_QUEUE_NAME
    assert "process_session_progression_job" in _function_names(
        ProgressionWorkerSettings
    )


def test_attendance_worker_registration_imports_cleanly() -> None:
    assert AttendanceWorkerSettings.queue_name == ATTENDANCE_QUEUE_NAME
    assert "process_attendance_retention_job" in _function_names(
        AttendanceWorkerSettings
    )
