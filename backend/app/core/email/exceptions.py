"""Exceptions raised by the email delivery layer."""





from app.core.email.enums import EmailProvider


class EmailError(Exception):
    """Base exception for email delivery failures"""



class EmailValidationError(EmailError):
    """Raised when an email request is invalid"""


class EmailConfigurationError(EmailError):
    """Raised when the email delivery configuration is invalid"""



class EmailProviderError(EmailError):
    """Raised when an email provider rejects or fails a request."""

    def __init__(
        self,
        message: str,
        *,
        provider: EmailProvider,
        code: str | None = None,
        retryable: bool = False,
    ) -> None:
        # super().__init__(message) hands `message` up to EmailError -> Exception,
        # so it gets stored properly as self.args and shows up in str(exc) / tracebacks.
        # EmailError has no __init__ of its own, so this call lands directly on
        # Exception.__init__, which is the built-in that actually remembers the message.
        #
        # provider/code/retryable are NOT known to Exception, so we can't pass them
        # to super() — they're just set as plain attributes below, for our own code
        # to inspect later (e.g. `except EmailProviderError as e: if e.retryable: ...`).
        super().__init__(message)
        self.provider = provider
        self.code = code
        self.retryable = retryable