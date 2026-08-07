import logging

from app.config.logging import ContextFormatter


def test_context_formatter_appends_source_and_extra_fields():
    formatter = ContextFormatter(
        "%(asctime)s | %(levelname)-8s | source=%(source)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    record = logging.LogRecord(
        name="backend.app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="Application event",
        args=(),
        exc_info=None,
    )
    record.tenant_id = "tenant-123"

    output = formatter.format(record)

    assert "source=" in output
    assert "tenant_id='tenant-123'" in output
    assert output.count("source=") == 1


def test_context_formatter_uses_plain_output_for_uvicorn_access_records():
    formatter = ContextFormatter(
        "%(asctime)s | %(levelname)-8s | source=%(source)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=99,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:11409", "GET", "/openapi.json", "1.1", 200),
        exc_info=None,
    )

    output = formatter.format(record)

    assert 'uvicorn.access | 127.0.0.1:11409 - "GET /openapi.json HTTP/1.1" 200' in output
    assert "source=" not in output
