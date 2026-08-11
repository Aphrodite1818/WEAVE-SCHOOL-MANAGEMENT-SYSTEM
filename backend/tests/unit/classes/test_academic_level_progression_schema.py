from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.classes.schemas import AcademicLevelProgressionConfigureRequest


def test_progression_requires_next_level_or_terminal_flag() -> None:
    with pytest.raises(ValidationError):
        AcademicLevelProgressionConfigureRequest()


def test_progression_accepts_next_level() -> None:
    target = uuid4()
    payload = AcademicLevelProgressionConfigureRequest(next_level_id=target)
    assert payload.next_level_id == target
    assert payload.is_terminal is False


def test_progression_accepts_terminal_without_next_level() -> None:
    payload = AcademicLevelProgressionConfigureRequest(is_terminal=True)
    assert payload.next_level_id is None
    assert payload.is_terminal is True
