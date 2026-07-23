from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.utils.normalization import (
    normalize_class_name,
    normalized_class_name_key,
)
from app.modules.classes.schemas import ClassRoomResponse


def test_full_secondary_school_class_name_displays_with_word_spaces() -> None:
    assert (
        normalize_class_name("JUNIORSECONDARYSCHOOL1")
        == "JUNIOR SECONDARY SCHOOL 1"
    )
    assert (
        normalize_class_name("junior secondary school 1")
        == "JUNIOR SECONDARY SCHOOL 1"
    )


def test_full_secondary_school_class_name_key_remains_compact() -> None:
    assert (
        normalized_class_name_key("JUNIOR SECONDARY SCHOOL 1")
        == "JUNIORSECONDARYSCHOOL1"
    )


def test_short_class_code_display_is_preserved() -> None:
    assert normalize_class_name("jss 1") == "JSS1"
    assert normalized_class_name_key("jss 1") == "JSS1"


def test_classroom_response_normalizes_existing_compact_full_name() -> None:
    now = datetime.now(timezone.utc)

    response = ClassRoomResponse(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="JUNIORSECONDARYSCHOOL1",
        arm=None,
        next_class_id=None,
        is_terminal=False,
        teacher_membership_id=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    assert response.name == "JUNIOR SECONDARY SCHOOL 1"
