"""Typed requests, results, and provider contracts for email delivery."""

from dataclasses import dataclass

from app.core.email.enums import EmailCategory, EmailProvider
from app.core.email.exceptions import EmailValidationError


@dataclass(frozen=True, slots=True)
class EmailRequest:
    """Provider-independent request for sending an email."""

    to_email: str
    subject: str
    body: str

    category: EmailCategory = EmailCategory.TRANSACTIONAL
    is_html: bool = False
    reply_to: str | None = None

    # Optional SES message tags represented as key/value pairs.
    tags: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.to_email or not self.to_email.strip():
            raise EmailValidationError("to_email must be a non-empty string.")

        if not self.subject or not self.subject.strip():
            raise EmailValidationError("subject must be a non-empty string.")

        if not self.body or not self.body.strip():
            raise EmailValidationError("body must be a non-empty string.")

        if self.reply_to is not None and not self.reply_to.strip():
            raise EmailValidationError(
                "reply_to must be a non-empty string when provided."
            )

        for name, value in self.tags:
            if not name or not name.strip():
                raise EmailValidationError("Email tag names cannot be empty.")

            if not value or not value.strip():
                raise EmailValidationError(
                    f"Email tag '{name}' cannot have an empty value."
                )


@dataclass(frozen=True, slots=True)
class EmailRoute:
    """Resolved SES sender configuration for an email category."""

    category: EmailCategory
    sender_name: str
    sender_email: str
    configuration_set: str
    reply_to: str | None = None


@dataclass(frozen=True, slots=True)
class EmailDeliveryResult:
    """Result returned after a provider accepts an email."""

    provider: EmailProvider
    accepted: bool
    message_id: str | None = None
    request_id: str | None = None
