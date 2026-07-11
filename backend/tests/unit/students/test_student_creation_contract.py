"""Regression tests for the tenant-admin student creation contract."""

from app.modules.students.schemas import StudentCreate


def test_student_create_exposes_optional_passport_photo_url() -> None:
    """The service may safely read the optional media field when it is omitted."""

    payload = StudentCreate(first_name="Taiwo", last_name="Ayimora")

    assert payload.passport_photo_url is None


def test_student_create_normalizes_optional_strings() -> None:
    """Blank optional form values should become None instead of invalid data."""

    payload = StudentCreate(
        first_name="  Taiwo  ",
        last_name="  Ayimora  ",
        state_of_origin="   ",
        arm="  A  ",
        passport_photo_url="   ",
    )

    assert payload.first_name == "Taiwo"
    assert payload.last_name == "Ayimora"
    assert payload.state_of_origin is None
    assert payload.arm == "A"
    assert payload.passport_photo_url is None
