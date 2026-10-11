"""Refresh-token session storage: issue, rotate, revoke, clean up.

The JWT alone is not enough to authenticate a refresh: every token also has a
row here holding ``sha256(jti)``. Rotation revokes the presented row and issues
a new one; presenting a row that is already revoked means the token was stolen
or replayed, so the caller revokes every un-revoked token for that user (the
whole chain) and rejects the request.

Nothing in this module commits: rows are staged in the caller's open
transaction so a login / rotation / password change either publishes its token
change together with the rest of the request or not at all.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.auth.security import (
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
    create_refresh_token,
)
from backend.app.models.refresh_token import RefreshToken
from backend.app.models.user import User

logger = logging.getLogger(__name__)

REFRESH_TOKEN_TYPE = "refresh"


def hash_jti(jti: str) -> str:
    """Hash the token identifier so the database never stores it directly."""
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def issue_refresh_token(db: Session, user: User) -> str:
    """Stage a new refresh token for `user` and return the plaintext token.

    The caller commits. The stored row keeps only the hashed jti and the
    expiry taken from the token itself.
    """
    jti = secrets.token_urlsafe(32)

    token = create_refresh_token({
        "sub": str(user.id),
        "role": user.role.value,
        "jti": jti,
    })

    db.add(
        RefreshToken(
            user_id=user.id,
            jti_hash=hash_jti(jti),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )

    return token


def decode_refresh_token(token: str, verify_exp: bool = True) -> dict | None:
    """Decode a refresh JWT, or None when it is unusable.

    `verify_exp=False` is only for logout: revoking a token whose clock has
    already run out must still work, and the row check that follows is what
    actually authorises the revocation.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": verify_exp},
        )
    except JWTError:
        return None

    if (
        payload.get("type") != REFRESH_TOKEN_TYPE
        or not payload.get("sub")
        or not payload.get("jti")
    ):
        return None

    return payload


def find_refresh_token(db: Session, jti: str) -> RefreshToken | None:
    """Live (unexpired) row behind a jti, or None.

    The expiry test happens in SQL, not in Python: both sides of the
    comparison then pass through the dialect's own datetime processor, so it
    behaves identically on Postgres (timestamptz) and on any other backend.
    An expired row is treated exactly like an unknown one — it cannot be
    refreshed either way.
    """
    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.jti_hash == hash_jti(jti),
            RefreshToken.expires_at >= datetime.now(timezone.utc),
        )
        .first()
    )


def revoke_refresh_token(db: Session, row: RefreshToken) -> bool:
    """Stamp `revoked_at` if the row is still live. True when this call did it.

    The conditional UPDATE makes concurrent rotation safe: exactly one of two
    racing requests can retire the row, the loser sees False and is treated as
    a reuse attempt.
    """
    revoked = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.id == row.id,
            RefreshToken.revoked_at.is_(None),
        )
        .update(
            {RefreshToken.revoked_at: datetime.now(timezone.utc)},
            synchronize_session=False,
        )
    )

    return revoked == 1


def revoke_user_refresh_tokens(db: Session, user_id) -> int:
    """Revoke every live refresh token of a user. Staged; caller commits.

    Used on password change, password reset and deactivation: those events
    mean the old sessions must stop working immediately.
    """
    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .update(
            {RefreshToken.revoked_at: datetime.now(timezone.utc)},
            synchronize_session=False,
        )
    )


def revoke_refresh_token_by_value(db: Session, token: str) -> bool:
    """Revoke the row behind a presented token (used by logout).

    Returns True when a live row was revoked. An unknown or malformed token is
    a no-op: logout is idempotent and must never reveal whether the token was
    still valid.
    """
    payload = decode_refresh_token(token, verify_exp=False)

    if payload is None:
        return False

    row = find_refresh_token(db, payload["jti"])

    if row is None:
        return False

    return revoke_refresh_token(db, row)


def cleanup_expired_refresh_tokens(db: Session) -> int:
    """Delete rows whose token can no longer be used anyway.

    Runs inside the existing in-process maintenance loop. Revoked-but-unexpired
    rows are kept: they are what detects a replay of a rotated token.
    """
    deleted = (
        db.query(RefreshToken)
        .filter(RefreshToken.expires_at < datetime.now(timezone.utc))
        .delete(synchronize_session=False)
    )

    db.commit()

    if deleted:
        logger.info("Deleted %s expired refresh token rows", deleted)

    return deleted
