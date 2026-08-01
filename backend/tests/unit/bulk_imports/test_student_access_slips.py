import re
from io import BytesIO

from openpyxl import load_workbook

from app.modules.bulk_imports.result_writer import (
    convert_value_for_csv,
    create_student_access_slip_report,
    write_xlsx_bytes,
)


def test_student_access_slips_escape_dynamic_values() -> None:
    report = create_student_access_slip_report(
        school_name="Taiwo & Sons <School>",
        result_rows=[
            {
                "row_number": 2,
                "status": "created",
                "first_name": "<script>alert(1)</script>",
                "last_name": '"Quoted" Student & Parent',
                "admission_number": "<img src=x onerror=alert(1)>",
                "class_name": "<svg onload=alert(1)>",
                "class_arm": '" onmouseover="alert(1)',
                "setup_code": "123456",
                "access_code_expires_at": "2026-07-29T12:00:00Z",
            }
        ],
    )

    html = report.content_bytes.decode("utf-8")

    assert "<script>alert(1)</script>" not in html
    assert "<img src=x onerror=alert(1)>" not in html
    assert "<svg onload=alert(1)>" not in html
    assert '" onmouseover="alert(1)' not in html
    assert "Taiwo &amp; Sons &lt;School&gt;" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&lt;svg onload=alert(1)&gt;" in html
    assert "&quot;Quoted&quot; Student &amp; Parent" in html
    assert "<script" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "onclick" not in html.lower()
    assert re.search(r"<[^>]+\son[a-z]+\s*=", html.lower()) is None


def test_spreadsheet_formula_prefixes_are_written_as_literals() -> None:
    rows = [
        {
            "first_name": '=HYPERLINK("http://example.test")',
            "class_name": "+JSS1",
            "error_message": "@bad formula",
            "row_number": 2,
        }
    ]

    assert convert_value_for_csv("-starts-with-minus") == "'-starts-with-minus"
    assert convert_value_for_csv(42) == "42"

    workbook = load_workbook(BytesIO(write_xlsx_bytes(rows=rows, headers=list(rows[0]))))
    sheet = workbook.active

    assert sheet["A2"].value.startswith("'=")
    assert sheet["B2"].value.startswith("'+")
    assert sheet["C2"].value.startswith("'@")
