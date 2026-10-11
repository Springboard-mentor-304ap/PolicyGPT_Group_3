"""Account-security e-mails sent to the account owner.

Follows the same never-fail convention as the password-reset and verification
mails: a delivery problem is logged and swallowed, because the password has
already been changed and the user must not be told the change failed.
"""

import logging

from backend.app.notifications.service import send_email

logger = logging.getLogger(__name__)

SUBJECT = "Your PolicyGPT password was changed"


def send_password_changed_email(email: str) -> bool:
    """Notify the account owner that their password was changed.

    Returns True when the mail was handed to the SMTP server. Any failure is
    logged and reported as False — never raised — so the request that
    triggered it (change-password / reset-password) always succeeds.
    """
    body = (
        "Your PolicyGPT password was changed.\n\n"
        "If this was you, no further action is needed.\n"
        "If you did not change your password, please reset it immediately "
        "using \"Forgot password\" on the sign-in page."
    )

    try:
        send_email(
            to_email=email,
            subject=SUBJECT,
            body=body,
        )
    except Exception as error:  # noqa: BLE001 - never break the request
        logger.warning(
            "Password-changed e-mail for %s could not be sent: %s",
            email,
            error,
        )
        return False

    return True
