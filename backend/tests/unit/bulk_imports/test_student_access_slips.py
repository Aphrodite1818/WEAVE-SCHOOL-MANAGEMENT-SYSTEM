from app.modules.bulk_imports.result_writer import create_student_access_slip_report


def test_student_access_slips_escape_dynamic_values() -> None:
    report = create_student_access_slip_report(
        school_name='Taiwo & Sons <School>',
        result_rows=[
            {
                "row_number": 2,
                "status": "created",
                "first_name": '<script>alert(1)</script>',
                "last_name": '"Quoted" Student & Parent',
                "admission_number": '<img src=x onerror=alert(1)>',
                "class_name": '<svg onload=alert(1)>',
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
