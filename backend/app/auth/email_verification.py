"""6-digit e-mail verification codes.

Registrations and resends issue a 6-digit code that is sent through the
existing Brevo SMTP mailer (`notifications.service.send_email`) and printed to
the backend console for local testing.

Storage reuses the existing `users.email_verification_token` column: the code
itself is stored as a bcrypt hash (the same hashing the passwords use) next to
its expiry, as ``<hash>:<unix-expiry>``, so no schema change is needed and the
plaintext code never touches the database.
"""

import logging
import os
import secrets
import time

from backend.app.auth.security import hash_password, verify_password
from backend.app.notifications.service import send_email
from backend.app.models.user import User

logger = logging.getLogger(__name__)

# Same lifetime the previous verification JWT had.
EMAIL_VERIFICATION_CODE_TTL_HOURS = 24
CODE_LENGTH = 6

_SEPARATOR = ":"


class VerificationCodeError(Exception):
    """Raised when a submitted code cannot be accepted.

    The message is safe to return to the client.
    """


def generate_verification_code() -> str:
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


def store_verification_code(user: User, code: str) -> None:
    """Persist the hashed code plus its expiry on the user row."""
    expires_at = int(
        time.time() + EMAIL_VERIFICATION_CODE_TTL_HOURS * 60 * 60
    )

    user.email_verification_token = (
        f"{hash_password(code)}{_SEPARATOR}{expires_at}"
    )


def verification_code_matches(user: User, code: str) -> bool:
    """Check a submitted code against the stored hash and expiry.

    Raises VerificationCodeError with a client-safe message for an expired or
    missing code, and returns False when the code itself is wrong.
    """
    stored = user.email_verification_token

    if not stored or _SEPARATOR not in stored:
        raise VerificationCodeError(
            "No verification code is pending for this account. "
            "Request a new code."
        )

    code_hash, _, expiry = stored.rpartition(_SEPARATOR)

    if not expiry.isdigit() or int(expiry) < time.time():
        raise VerificationCodeError(
            "The verification code has expired. Request a new code."
        )

    return verify_password(code, code_hash)


def send_verification_code(email: str, code: str) -> bool:
    """Email the code and log it for local testing.

    Returns True when the mail was handed to the SMTP server. A mail failure
    never fails the caller: the request stays successful and the failure is
    reported in the log.
    """
    if os.getenv("ENVIRONMENT", "").strip().lower() != "production":
        print(f"[DEV] Email verification code for {email}: {code}", flush=True)

    subject = "Your PolicyGPT verification code"
    body = (
        f"Your PolicyGPT email verification code is {code}.\n\n"
        f"It expires in {EMAIL_VERIFICATION_CODE_TTL_HOURS} hours. "
        "If you did not create this account you can ignore this email."
    )

    try:
        send_email(
            to_email=email,
            subject=subject,
            body=body,
        )
    except Exception as error:  # noqa: BLE001 - never break registration
        logger.warning(
            "Verification e-mail for %s could not be sent: %s. "
            "The code is available in the backend console.",
            email,
            error,
        )
        return False

    return True
