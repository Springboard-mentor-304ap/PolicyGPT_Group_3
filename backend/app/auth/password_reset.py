"""Single-use password reset tokens.

The token is a short-lived JWT whose only secret material is a random `jti`.
The database stores ``<sha256(jti)>:<unix-expiry>`` on the user row, so a
leaked database never contains a usable token, and the stored value is cleared
the moment the token is redeemed — the token therefore works exactly once.

The plaintext token is only ever delivered by e-mail; the API response stays
generic so it cannot be used to probe which addresses are registered.
"""

import hashlib
import logging
import os
import secrets
import time

from jose import jwt

from backend.app.auth.security import ALGORITHM, SECRET_KEY
from backend.app.models.user import User
from backend.app.notifications.service import send_email

logger = logging.getLogger(__name__)

PASSWORD_RESET_TOKEN_TTL_MINUTES = 15

_SEPARATOR = ":"


def _hash_jti(jti: str) -> str:
    """Hash the token identifier so the database never stores it directly."""

    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def create_password_reset_token(user_id) -> tuple[str, str]:
    """Create a reset token and return ``(token, jti)``.

    The jti is stored (hashed) with an expiry by
    :func:`store_password_reset_token`; the token itself is e-mailed.
    """

    jti = secrets.token_urlsafe(32)
    expires_at = int(time.time() + PASSWORD_RESET_TOKEN_TTL_MINUTES * 60)

    token = jwt.encode(
        {
            "sub": str(user_id),
            "jti": jti,
            "exp": expires_at,
            "type": "password_reset",
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return token, jti


def store_password_reset_token(user: User, jti: str) -> None:
    """Persist the hashed jti plus its expiry on the user row."""

    expires_at = int(time.time() + PASSWORD_RESET_TOKEN_TTL_MINUTES * 60)

    user.password_reset_token = (
        f"{_hash_jti(jti)}{_SEPARATOR}{expires_at}"
    )


def password_reset_token_matches(user: User, jti: str | None) -> bool:
    """True when the jti matches the pending, unexpired reset token."""

    if not jti:
        return False

    stored = user.password_reset_token

    if not stored or _SEPARATOR not in stored:
        return False

    digest, _, expiry = stored.rpartition(_SEPARATOR)

    if not expiry.isdigit() or int(expiry) < time.time():
        return False

    return secrets.compare_digest(digest, _hash_jti(jti))


def clear_password_reset_token(user: User) -> None:
    """Drop the stored token so it can never be redeemed twice."""

    user.password_reset_token = None


def _frontend_reset_url(token: str) -> str:
    base_url = os.getenv(
        "FRONTEND_BASE_URL",
        "http://localhost:4200",
    ).rstrip("/")

    return f"{base_url}/reset-password?token={token}"


def send_password_reset_email(email: str, token: str) -> bool:
    """E-mail the reset link and log it for local testing.

    Returns True when the mail was handed to the SMTP server. A mail failure
    never fails the caller: the response stays generic and the failure is
    reported in the log (same convention as e-mail verification codes).
    """

    reset_url = _frontend_reset_url(token)

    # The API never returns the token, so the backend console is the local
    # testing equivalent of opening the e-mail.
    print(
        f"[DEV] Password reset link for {email}: {reset_url}",
        flush=True,
    )

    subject = "Reset your PolicyGPT password"
    body = (
        "We received a request to reset your PolicyGPT password.\n\n"
        f"Open this link to choose a new password:\n{reset_url}\n\n"
        f"The link expires in {PASSWORD_RESET_TOKEN_TTL_MINUTES} minutes "
        "and can only be used once. If you did not request a reset you can "
        "ignore this email."
    )

    try:
        send_email(
            to_email=email,
            subject=subject,
            body=body,
        )
    except Exception as error:  # noqa: BLE001 - never break the request
        logger.warning(
            "Password reset e-mail for %s could not be sent: %s. "
            "The reset link is available in the backend console.",
            email,
            error,
        )
        return False

    return True
