"""Email categories and provider-related enumerations."""

from enum import Enum as PyEnum


class EmailProvider(str, PyEnum):
    "Supported email delivery providers"

    LEGACY = "legacy"
    SES = "ses"


class EmailCategory(str, PyEnum):
    """ "Email categories used for sender and configuration-set routing"""

    TRANSACTIONAL = "transactional"
    SECURITY = "security"
    BULK = "bulk"
