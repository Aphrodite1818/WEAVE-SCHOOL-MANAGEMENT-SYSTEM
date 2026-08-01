from app.modules.bulk_imports.models import ImportJob, ImportResourceType
from app.modules.bulk_imports.service import build_import_source_fingerprint


def test_import_source_fingerprint_is_stable_for_equivalent_rows() -> None:
    rows = [
        (3, {"first_name": "Ada", "last_name": "Okafor", "class_id": "class-1"}),
        (2, {"first_name": "Tunde", "last_name": "Bello", "class_id": "class-2"}),
    ]
    first = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=rows,
    )
    second = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=list(reversed(rows)),
    )
    assert first == second
    assert len(first) == 64


def test_import_source_fingerprint_changes_when_student_data_changes() -> None:
    original = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[(2, {"first_name": "Ada", "last_name": "Okafor"})],
    )
    changed = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[(2, {"first_name": "Ada", "last_name": "Bello"})],
    )
    assert original != changed


def test_confirmed_fingerprint_has_unique_tenant_resource_index() -> None:
    index = next(
        item
        for item in ImportJob.__table__.indexes
        if item.name == "uq_import_jobs_tenant_confirmed_fingerprint"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "tenant_id",
        "resource_type",
        "confirmed_fingerprint",
    ]
