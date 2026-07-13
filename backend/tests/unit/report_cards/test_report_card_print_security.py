import inspect

from app.modules.report_cards import router
from app.modules.report_cards.service import ReportCardService


def test_report_card_html_response_headers_prevent_sensitive_caching():
    headers = router.REPORT_CARD_HTML_HEADERS

    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in headers["Content-Security-Policy"]


def test_report_card_data_response_headers_prevent_sensitive_caching():
    headers = router.REPORT_CARD_DATA_HEADERS

    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"


def test_report_card_html_template_has_no_inline_print_handler():
    source = inspect.getsource(ReportCardService.render_html)

    assert "onclick=" not in source
    assert "document.write" not in source
    assert "dangerouslySetInnerHTML" not in source
