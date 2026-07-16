"""Public authentication service facade.

The implementation is split by responsibility to keep account authentication,
OTP flows, and persistent sessions independently testable.
"""

from app.modules.auth.login_service import AuthService
from app.modules.auth.otp_service import OTPService, TenantActivationService, UserInviteService
from app.modules.auth.session_service import (
    AuthenticatedActor,
    AuthSessionService,
    AuthSessionTokenPair,
)

__all__ = [
    "AuthenticatedActor",
    "AuthService",
    "AuthSessionService",
    "AuthSessionTokenPair",
    "OTPService",
    "TenantActivationService",
    "UserInviteService",
]
