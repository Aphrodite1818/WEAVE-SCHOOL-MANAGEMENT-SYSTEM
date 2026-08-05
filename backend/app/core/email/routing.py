"""Resolve email categories to approved senders and SES configuration sets."""




from app.config.settings import Settings, settings 
from app.core.email.contracts import EmailRoute
from app.core.email.enums import EmailCategory
from app.core.email.exceptions import EmailConfigurationError


def _has_value(value : str | None) -> bool:
    return bool(value and value.strip()) #short circuit to avoid calling .strip() on None



def resolve_email_route(
    category : EmailCategory,
    *,
    config : Settings = settings
) -> EmailRoute:
    """Return sender and configuration-set details for an email category"""


    if category == EmailCategory.TRANSACTIONAL:
        sender_email  = config.SES_TRANSACTIONAL_FROM_EMAIL
        configuration_set = config.SES_TRANSACTIONAL_CONFIGURATION_SET


    elif category == EmailCategory.SECURITY:
        sender_email  = config.SES_SECURITY_FROM_EMAIL
        configuration_set = config.SES_SECURITY_CONFIGURATION_SET


    elif category == EmailCategory.BULK:
        sender_email  = config.SES_BULK_FROM_EMAIL
        configuration_set = config.SES_BULK_CONFIGURATION_SET


    else:
        raise EmailConfigurationError(
            f"Unsupported email category: {category}",
        )


    if not _has_value(sender_email):
        raise EmailConfigurationError(
            f"Missing sender email for category {category}",
        )


    if not _has_value(configuration_set):
        raise EmailConfigurationError(
            f"Missing SES configuration set for category {category}",
        )
    



    reply_to = (
        config.EMAIL_REPLY_TO.strip()
        if _has_value(config.EMAIL_REPLY_TO)
        else None
    )



    return EmailRoute(
        category=category,
        sender_name=config.EMAIL_SENDER_NAME.strip(),
        sender_email=sender_email.strip(),
        configuration_set=configuration_set.strip(),
        reply_to=reply_to,
    )