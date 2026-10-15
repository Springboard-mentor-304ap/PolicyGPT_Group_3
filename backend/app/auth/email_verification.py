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
from datetime import datetime, timezone

from backend.app.auth.security import hash_password, verify_password
from backend.app.notifications.service import send_email
from backend.app.models.user import User

logger = logging.getLogger(__name__)

# A 6-digit code must not stay valid for long: 5 digits of entropy is only
# safe with a short lifetime and an attempt limit (both enforced below and
# in backend/app/auth/router.py). Env-configurable for tests/ops.
def _code_ttl_minutes() -> int:
    raw = os.getenv("EMAIL_VERIFICATION_CODE_TTL_MINUTES", "").strip()
    try:
        minutes = int(raw) if raw else 15
    except ValueError:
        minutes = 15
    return max(1, minutes)


CODE_LENGTH = 6

# Wrong guesses a single pending code tolerates. The router increments the
# counter atomically in SQL; on the fifth wrong guess the code is invalidated
# and a new one must be requested.
MAX_VERIFICATION_ATTEMPTS = 5

# A new code may be issued at most once per this many seconds per account.
# A resend inside the window returns the normal success message without
# issuing (or resetting) anything, so the response cannot be used to probe
# whether an account exists.
RESEND_COOLDOWN_SECONDS = 60

_SEPARATOR = ":"


def resend_cooldown_active(user: User) -> bool:
    """True when a code was issued for this account less than a cooldown ago."""

    sent_at = user.email_verification_sent_at

    if sent_at is None:
        return False

    # SQLite hands naive datetimes back for tz-aware columns; treat them as
    # UTC so the cooldown cannot be bypassed by a host-TZ quirk.
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    age = (datetime.now(timezone.utc) - sent_at).total_seconds()

    return age < RESEND_COOLDOWN_SECONDS


class VerificationCodeError(Exception):
    """Raised when a submitted code cannot be accepted.

    The message is safe to return to the client.
    """


def generate_verification_code() -> str:
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


def store_verification_code(user: User, code: str) -> None:
    """Persist the hashed code plus its expiry on the user row.

    Issuing a new code also resets the wrong-guess counter and stamps the
    resend cooldown — a fresh code must not inherit the previous code's
    failed attempts.
    """
    expires_at = int(time.time() + _code_ttl_minutes() * 60)

    user.email_verification_token = (
        f"{hash_password(code)}{_SEPARATOR}{expires_at}"
    )
    user.email_verification_attempts = 0
    user.email_verification_sent_at = datetime.now(timezone.utc)


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
        f"It expires in {_code_ttl_minutes()} minutes. "
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
