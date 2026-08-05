from __future__ import annotations

import pytest

from app.core.email.contracts import EmailRequest
from app.core.email.enums import EmailCategory
from app.core.email.exceptions import EmailValidationError


def test_email_request_accepts_valid_provider_independent_data() -> None:
    request = EmailRequest(
        to_email="user@example.com",
        subject="Welcome",
        body="Hello",
        category=EmailCategory.TRANSACTIONAL,
        reply_to="support@example.com",
        tags=(("email_type", "welcome"),),
    )

    assert request.to_email == "user@example.com"
    assert request.category == EmailCategory.TRANSACTIONAL
    assert request.tags == (("email_type", "welcome"),)


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("to_email", " "),
        ("subject", " "),
        ("body", " "),
    ],
)
def test_email_request_rejects_blank_required_fields(
    field_name: str,
    field_value: str,
) -> None:
    values = {
        "to_email": "user@example.com",
        "subject": "Subject",
        "body": "Body",
    }
    values[field_name] = field_value

    with pytest.raises(EmailValidationError):
        EmailRequest(**values)


def test_email_request_rejects_blank_reply_to() -> None:
    with pytest.raises(EmailValidationError):
        EmailRequest(
            to_email="user@example.com",
            subject="Subject",
            body="Body",
            reply_to=" ",
        )


@pytest.mark.parametrize(
    "tags",
    [
        (("", "value"),),
        (("name", ""),),
    ],
)
def test_email_request_rejects_blank_tag_components(
    tags: tuple[tuple[str, str], ...],
) -> None:
    with pytest.raises(EmailValidationError):
        EmailRequest(
            to_email="user@example.com",
            subject="Subject",
            body="Body",
            tags=tags,
        )
