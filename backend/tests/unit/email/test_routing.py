from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.email.enums import EmailCategory
from app.core.email.exceptions import EmailConfigurationError
from app.core.email.routing import resolve_email_route


def _config(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "EMAIL_SENDER_NAME": "WEAVE",
        "EMAIL_REPLY_TO": "support@weavecloudspace.com",
        "SES_TRANSACTIONAL_FROM_EMAIL": "no-reply@notifications.weavecloudspace.com",
        "SES_SECURITY_FROM_EMAIL": "security@notifications.weavecloudspace.com",
        "SES_BULK_FROM_EMAIL": "updates@updates.weavecloudspace.com",
        "SES_TRANSACTIONAL_CONFIGURATION_SET": "weave-transactional",
        "SES_SECURITY_CONFIGURATION_SET": "weave-security",
        "SES_BULK_CONFIGURATION_SET": "weave-bulk",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    ("category", "sender", "configuration_set"),
    [
        (
            EmailCategory.TRANSACTIONAL,
            "no-reply@notifications.weavecloudspace.com",
            "weave-transactional",
        ),
        (
            EmailCategory.SECURITY,
            "security@notifications.weavecloudspace.com",
            "weave-security",
        ),
        (
            EmailCategory.BULK,
            "updates@updates.weavecloudspace.com",
            "weave-bulk",
        ),
    ],
)
def test_resolve_email_route_by_category(
    category: EmailCategory,
    sender: str,
    configuration_set: str,
) -> None:
    route = resolve_email_route(category, config=_config())

    assert route.category == category
    assert route.sender_name == "WEAVE"
    assert route.sender_email == sender
    assert route.configuration_set == configuration_set
    assert route.reply_to == "support@weavecloudspace.com"


def test_resolve_email_route_rejects_missing_sender() -> None:
    with pytest.raises(EmailConfigurationError):
        resolve_email_route(
            EmailCategory.SECURITY,
            config=_config(SES_SECURITY_FROM_EMAIL=" "),
        )


def test_resolve_email_route_rejects_missing_configuration_set() -> None:
    with pytest.raises(EmailConfigurationError):
        resolve_email_route(
            EmailCategory.BULK,
            config=_config(SES_BULK_CONFIGURATION_SET=" "),
        )
