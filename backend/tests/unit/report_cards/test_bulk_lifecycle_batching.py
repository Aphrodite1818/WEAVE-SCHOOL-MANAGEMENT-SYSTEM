import inspect

from app.modules.report_cards.bulk_service import (
    BULK_REPORT_LIFECYCLE_BATCH_SIZE,
    BulkReportCardService,
)
from app.modules.report_cards.service import ReportCardService


def test_bulk_report_lifecycle_uses_bounded_batches_and_savepoints() -> None:
    assert BULK_REPORT_LIFECYCLE_BATCH_SIZE == 50

    for method in (
        BulkReportCardService.publish,
        BulkReportCardService.archive,
        BulkReportCardService.reopen,
    ):
        source = inspect.getsource(method)
        assert "BULK_REPORT_LIFECYCLE_BATCH_SIZE" in source
        assert "db.begin_nested()" in source
        assert "await db.commit()" in source


def test_bulk_publish_reuses_publish_validation_without_inner_commit() -> None:
    bulk_source = inspect.getsource(BulkReportCardService.publish)
    publish_signature = inspect.signature(ReportCardService.publish)

    assert "commit=False" in bulk_source
    assert "commit" in publish_signature.parameters
    assert publish_signature.parameters["commit"].default is True


def test_bulk_scope_is_frozen_before_batched_mutation() -> None:
    for method in (
        BulkReportCardService.publish,
        BulkReportCardService.archive,
        BulkReportCardService.reopen,
    ):
        source = inspect.getsource(method)
        assert "_scope_card_ids" in source
        assert "batch_ids = card_ids[" in source
