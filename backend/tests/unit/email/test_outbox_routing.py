from __future__ import annotations

from types import SimpleNamespace

from app.core.email.enums import EmailCategory
from app.modules.email_outbox.service import (
    build_outbox_email_tags,
    resolve_outbox_email_category,
)


def test_bulk_import_outbox_email_uses_bulk_category() -> None:
    email_item = SimpleNamespace(
        metadata_json={"source": "bulk_import"},
        template_name="parent_invitation",
    )

    assert resolve_outbox_email_category(email_item) == EmailCategory.BULK
    assert build_outbox_email_tags(email_item) == (("email_type", "parent_invitation"),)


def test_normal_outbox_email_uses_transactional_category() -> None:
    email_item = SimpleNamespace(
        metadata_json={},
        template_name="teacher_invitation",
    )

    assert resolve_outbox_email_category(email_item) == EmailCategory.TRANSACTIONAL
