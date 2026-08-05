"""Typed requests, results, and provider contracts for email delivery."""




from dataclasses import dataclass 
from app.core.email.enums import EmailCategory, EmailProvider




"""
Internal data contracts for the email delivery pipeline.

The dataclasses in this module represent the information passed between
the email dispatcher, routing logic, and delivery providers.

1. EmailRequest
   Represents an email prepared for delivery, including its recipient,
   subject, body, category, content type, optional reply-to address,
   and provider-specific tags.

2. EmailRoute
   Represents the sender configuration resolved for an email category,
   including the sender identity, reply-to address, and optional SES
   configuration set.

3. EmailDeliveryResult
   Represents the outcome of a delivery attempt, including the provider
   used, whether the email was accepted, and any provider message or
   request identifiers.

The typical flow is:

    EmailRequest
        -> route resolution
        -> provider delivery
        -> EmailDeliveryResult
"""

@dataclass(frozen=True, slots = True)
class EmailRequest:
    """Provider-independent request for sending an email"""

    to_email : str
    subject : str 
    body : str

    category : EmailCategory = EmailCategory.TRANSACTIONAL
    is_html : bool = False
    reply_to : str | None = None

    # Optional labels attached to this email (e.g. ("email_type", "password_reset")).
    # Used by SES to tag delivery/bounce/complaint events so they can be filtered
    # and tracked separately in CloudWatch metrics and event notifications.
    # Sending still works the same either way — tags just make it possible to
    # answer questions like "how many welcome emails bounced this month?" later.
    # Note: SES only allows letters, numbers, "-", and "_" in tag names/values.
    tags : tuple[tuple[str , str], ...] = ()    #e.g (("email_type", "password_reset"), ("user_id", "12345"))


    def __post_init__(self) -> None:
        if not self.to_email or not self.to_email.strip():
            raise ValueError("to_email must be a non-empty string")


        if not self.subject or not self.subject.strip():
            raise ValueError("subject must be a non-empty string")




        if not self.body or not self.body.strip():
            raise ValueError("body must be a non-empty string")


        if self.reply_to is not None and not self.reply_to.strip():
            raise ValueError("reply_to must be a non-empty string if provided")

        for name , value in self.tags:
            if not name or not name.strip():
                raise ValueError("Email tag names cannot be empty")

            if not value or not value.strip():
                raise ValueError(f"Email tag '{name}' cannot have an empty value")





@dataclass(frozen=True, slots = True)
class EmailRoute:
    """
    Resolved sender configuration for an email category
    consumed by resolve_email_route() and passed to the provider for delivery.
    """


    category : EmailCategory
    sender_name : str
    sender_email : str
    configuration_set : str 
    reply_to : str | None = None




@dataclass(frozen=True, slots = True)
class EmailDeliveryResult:
    """Result returned after  provider accepts email """


    provider : EmailProvider
    accepted : bool
    message_id : str | None = None
    request_id : str | None = None