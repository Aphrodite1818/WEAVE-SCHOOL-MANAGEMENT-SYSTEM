"""Resolve email categories to provider-specific sender routes."""

from app.config.settings import Settings, settings
from app.core.email.contracts import EmailRoute
from app.core.email.enums import EmailCategory, EmailProvider
from app.core.email.exceptions import EmailConfigurationError


def _has_value(value: str | None) -> bool:
    return bool(value and value.strip())


def resolve_email_route(
    category: EmailCategory,
    *,
    provider: EmailProvider = EmailProvider.SES,
    config: Settings = settings,
) -> EmailRoute:
    """Return sender and optional provider metadata for one email category."""

    if provider == EmailProvider.RESEND:
        sender_by_category = {
            EmailCategory.TRANSACTIONAL: config.RESEND_TRANSACTIONAL_FROM_EMAIL,
            EmailCategory.SECURITY: config.RESEND_SECURITY_FROM_EMAIL,
            EmailCategory.BULK: config.RESEND_BULK_FROM_EMAIL,
        }
        configuration_set = ""
    elif provider == EmailProvider.SES:
        sender_by_category = {
            EmailCategory.TRANSACTIONAL: config.SES_TRANSACTIONAL_FROM_EMAIL,
            EmailCategory.SECURITY: config.SES_SECURITY_FROM_EMAIL,
            EmailCategory.BULK: config.SES_BULK_FROM_EMAIL,
        }
        configuration_set_by_category = {
            EmailCategory.TRANSACTIONAL: config.SES_TRANSACTIONAL_CONFIGURATION_SET,
            EmailCategory.SECURITY: config.SES_SECURITY_CONFIGURATION_SET,
            EmailCategory.BULK: config.SES_BULK_CONFIGURATION_SET,
        }
        configuration_set = configuration_set_by_category.get(category, "")
    else:
        raise EmailConfigurationError(
            f"Provider {provider.value!r} does not use category sender routing."
        )

    sender_email = sender_by_category.get(category)
    if sender_email is None:
        raise EmailConfigurationError(f"Unsupported email category: {category}")
    if not _has_value(sender_email):
        raise EmailConfigurationError(f"Missing sender email for category {category}")
    if provider == EmailProvider.SES and not _has_value(configuration_set):
        raise EmailConfigurationError(f"Missing SES configuration set for category {category}")

    reply_to = config.EMAIL_REPLY_TO.strip() if _has_value(config.EMAIL_REPLY_TO) else None
    return EmailRoute(
        category=category,
        sender_name=config.EMAIL_SENDER_NAME.strip(),
        sender_email=sender_email.strip(),
        configuration_set=configuration_set.strip(),
        reply_to=reply_to,
    )
