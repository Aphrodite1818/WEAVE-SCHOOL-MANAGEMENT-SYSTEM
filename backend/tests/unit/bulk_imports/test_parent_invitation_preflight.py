from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictException
from app.modules.auth.account_email_guard import AccountEmailGuard
from app.modules.bulk_imports.service import BulkImportService
from app.modules.bulk_imports.validators import ImportRowValidationResult
from app.modules.parents.repository import ParentAccountRepository


@pytest.mark.asyncio
async def test_parent_invitation_preflight_rejects_incompatible_role(monkeypatch) -> None:
    async def ensure_available(db, email, *, invited_actor_type):
        if email == "teacher@example.com":
            raise ConflictException("This email is already registered under another role.")
        return str(email).casefold()

    monkeypatch.setattr(
        AccountEmailGuard,
        "ensure_available_for_invitation_role",
        ensure_available,
    )
    get_parent_account = AsyncMock(return_value=SimpleNamespace(id="parent-account"))
    monkeypatch.setattr(ParentAccountRepository, "get_by_email", get_parent_account)

    valid_result = ImportRowValidationResult(
        row_number=2,
        raw_row={},
        normalized_row={
            "first_name": "Ada",
            "last_name": "Student",
            "parent_email_1": "PARENT@EXAMPLE.COM",
        },
    )
    conflict_result = ImportRowValidationResult(
        row_number=3,
        raw_row={},
        normalized_row={
            "first_name": "Grace",
            "last_name": "Student",
            "parent_email_1": "teacher@example.com",
        },
    )

    summary = await BulkImportService.preflight_student_parent_invitations(
        db=SimpleNamespace(),
        validation_results=[valid_result, conflict_result],
    )

    assert valid_result.normalized_row["parent_email_1"] == "parent@example.com"
    assert conflict_result.errors[0].error_code == "parent_email_role_conflict"
    assert summary == {
        "parent_emails_supplied": 2,
        "existing_parent_accounts": 1,
        "new_parent_invitations_expected": 1,
        "existing_pending_invitations": 0,
        "parent_links_expected_after_acceptance": 1,
    }
