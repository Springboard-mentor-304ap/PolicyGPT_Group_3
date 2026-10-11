from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from uuid import UUID

from backend.app.auth.security import (
    ALGORITHM,
    SECRET_KEY,
)
from backend.app.db.database import get_db
from backend.app.models.user import User


security = HTTPBearer()

# Same scheme, but a missing or unreadable Authorization header yields an
# anonymous caller instead of a 401. Used by public endpoints that also have
# to know whether the caller is a government official.
optional_security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        # Get user ID from token
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        # `sub` arrives as text; parse it here so the lookup never hands the
        # database a value it cannot compare against a UUID (and so a forged
        # sub that is not a UUID is a 401 rather than a server error).
        try:
            user_uuid = UUID(str(user_id))
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        # Only access tokens can authenticate API requests
        token_type = payload.get("type")

        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.get(User, user_uuid)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        optional_security
    ),
    db: Session = Depends(get_db),
) -> User | None:
    """The authenticated user when a valid bearer token was sent, else None.

    Public endpoints keep working for guests and for citizens/researchers;
    the returned user only narrows what a government official may see.
    """
    if credentials is None:
        return None

    try:
        return get_current_user(credentials=credentials, db=db)
    except HTTPException:
        # An expired or unreadable token is treated as an anonymous caller,
        # exactly like a missing header.
        return None