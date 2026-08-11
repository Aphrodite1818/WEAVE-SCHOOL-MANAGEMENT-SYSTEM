"""Regression tests for the tenant-admin student creation contract."""

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.students.schemas import StudentCreate


def test_student_create_does_not_accept_passport_media() -> None:
    """Passport media must be uploaded through the dedicated media endpoint."""

    with pytest.raises(ValidationError):
        StudentCreate(
            first_name="Taiwo",
            last_name="Ayimora",
            date_of_birth=date(2010, 1, 1),
            class_id=uuid4(),
            passport_photo_url="https://example.com/student.jpg",
        )


def test_student_create_normalizes_optional_strings() -> None:
    """Blank optional form values should become None instead of invalid data."""

    payload = StudentCreate(
        first_name="  Taiwo  ",
        last_name="  Ayimora  ",
        date_of_birth=date(2010, 1, 1),
        class_id=uuid4(),
        state_of_origin="   ",
    )

    assert payload.first_name == "Taiwo"
    assert payload.last_name == "Ayimora"
    assert payload.state_of_origin is None
