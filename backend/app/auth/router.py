import secrets
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from jose import JWTError, jwt

from backend.app.auth.account_emails import send_password_changed_email
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.refresh_tokens import (
    decode_refresh_token,
    find_refresh_token,
    issue_refresh_token,
    revoke_refresh_token,
    revoke_refresh_token_by_value,
    revoke_user_refresh_tokens,
)
from backend.app.auth.schemas import (
    ChangePasswordRequest,
    ForgetPasswordRequest,
    LogoutRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    ResetPasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    VerifyEmailRequest,
    ResendVerificationRequest,
    UserDetailsResponse,
    RegistrationResponse
)
from backend.app.auth.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)
from backend.app.auth.password_reset import (
    clear_password_reset_token,
    create_password_reset_token,
    password_reset_token_matches,
    send_password_reset_email,
    store_password_reset_token,
)
from backend.app.auth.email_verification import (
    CODE_LENGTH,
    MAX_VERIFICATION_ATTEMPTS,
    VerificationCodeError,
    generate_verification_code,
    resend_cooldown_active,
    send_verification_code,
    store_verification_code,
    verification_code_matches,
)
from backend.app.db.database import get_db
from backend.app.models.user import User, UserRole


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ─── E-MAIL NORMALIZATION ────────────────────────────────────────────────────

def normalize_email(email: str) -> str:
    """E-mails are stored and compared in lowercase.

    Addresses are case-insensitive, so `A@x.com` and `a@x.com` must never be
    two accounts.
    """
    return email.strip().lower()


def find_user_by_email(db: Session, email: str) -> User | None:
    """Case-insensitive lookup that also matches legacy mixed-case rows."""
    return (
        db.query(User)
        .filter(func.lower(User.email) == normalize_email(email))
        .first()
    )


# ─── REGISTER ────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    normalized_email = normalize_email(data.email)

    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    verification_code = generate_verification_code()

    user = User(
        full_name=data.full_name,
        email=normalized_email,
        password_hash=hash_password(data.password),
        role=UserRole.CITIZEN,
        is_active=True,
        email_verified=False,
    )

    # Only the hash of the code is stored; the code is e-mailed and printed to
    # the backend console for local testing.
    store_verification_code(user, verification_code)

    db.add(user)
    db.commit()
    db.refresh(user)

    send_verification_code(user.email, verification_code)

    return {
        "message": "Registration successful. Please verify your email."
    }                                                       


# ─── EMAIL VERIFICATION ─────────────────────────────────────────────────────

@router.post("/verify-email")
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    if data.code:
        if not data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Enter the 6-digit verification code together with the "
                    "email address it was sent to"
                ),
            )

        return _verify_email_code(db, data.email, data.code)

    if data.token:
        return _verify_email_token(db, data.token)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Enter the 6-digit verification code sent to your email",
    )


def _verify_email_code(
    db: Session,
    email: str,
    code: str,
) -> dict:
    """Verify the 6-digit code against the stored hash and expiry.

    Every failure returns the same generic message so the response never
    reveals whether the code was wrong, expired, or absent. Each guess is
    counted with one atomic ``UPDATE ... RETURNING`` (never read-modify-
    write in Python), so concurrent guesses cannot slip past the limit;
    after MAX_VERIFICATION_ATTEMPTS wrong guesses the code is invalidated
    and a new one must be requested.
    """
    generic_error = "Invalid or expired verification code"
    submitted = code.strip()

    if not submitted.isdigit() or len(submitted) != CODE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=generic_error,
        )

    user = find_user_by_email(db, email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=generic_error,
        )

    if user.email_verified:
        return {"message": "Email already verified"}

    # Count this guess before checking it. The guard on a still-pending code
    # means attempts against an invalidated (or never-issued) code do not
    # resurrect anything: they simply find no row and fail generically.
    attempts = db.execute(
        update(User)
        .where(
            User.id == user.id,
            User.email_verification_token.is_not(None),
        )
        .values(
            email_verification_attempts=(
                func.coalesce(User.email_verification_attempts, 0) + 1
            )
        )
        .returning(User.email_verification_attempts)
    ).scalar_one_or_none()
    db.commit()

    if attempts is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=generic_error,
        )

    try:
        code_is_valid = verification_code_matches(user, submitted)
    except VerificationCodeError:
        # Expired (or an unreadable stored value): same generic failure as a
        # wrong code, so responses reveal nothing extra.
        code_is_valid = False

    if code_is_valid:
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_attempts = None
        db.commit()

        return {"message": "Email verified successfully"}

    if attempts >= MAX_VERIFICATION_ATTEMPTS:
        # Lockout: burn the code so even a correct guess can no longer use
        # it, and tell the user how to recover.
        user.email_verification_token = None
        user.email_verification_attempts = None
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{generic_error}. Too many incorrect attempts — this code "
                "is no longer valid. Request a new verification code."
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=generic_error,
    )


def _verify_email_token(
    db: Session,
    token: str,
) -> dict:
    """Legacy direct-link verification (JWT sent in an older e-mail)."""
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        token_type = payload.get("type")
        email = payload.get("email")

        if token_type != "email_verification" or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    user = find_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.email_verified:
        return {"message": "Email already verified"}

    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_attempts = None
    db.commit()

    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
def resend_verification(
    data: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    user = find_user_by_email(db, data.email)
    if not user:
        # Don't reveal whether email exists
        return {"message": "If the email is registered, a verification code has been sent"}

    if user.email_verified:
        return {"message": "Email already verified"}

    # Per-account cooldown: a resend inside the window returns the exact
    # success message a real send would, without issuing a new code and
    # without resetting the attempt counter — so it reveals nothing and
    # cannot be used to stretch a guess window.
    if resend_cooldown_active(user):
        return {"message": "Verification code sent"}

    verification_code = generate_verification_code()
    store_verification_code(user, verification_code)
    db.commit()

    send_verification_code(user.email, verification_code)

    # The code is intentionally never returned: it is e-mailed and only
    # printed to the backend console.
    return {"message": "Verification code sent"}


# ─── LOGIN ───────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = find_user_by_email(db, data.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Policy: an account can only sign in after its e-mail address has been
    # verified. The check runs after the password check so it cannot be used
    # to probe whether an address is registered.
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Email not verified. Please verify your email address "
                "before logging in."
            ),
        )

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
    })

    # The refresh token is recorded (hashed) before it is handed out, so
    # every session is individually revocable and can be rotated.
    refresh_token = issue_refresh_token(db, user)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ─── REFRESH TOKEN ──────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
)
def refresh_token(
    data: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Rotate the caller's refresh token and return a fresh pair.

    The token travels in the request body — query strings leak into access
    logs and proxies. Each call revokes the presented row and issues a new
    one; presenting a row that is already revoked means the token was
    replayed, so every live token of that user is revoked as well.
    """
    payload = decode_refresh_token(data.refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    row = find_refresh_token(db, payload["jti"])

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.get(User, row.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Expiry is part of the lookup: an expired row is simply not found, so
    # it never reaches the rotation below.
    if not revoke_refresh_token(db, row):
        revoke_user_refresh_tokens(db, row.user_id)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
    })

    refresh_token = issue_refresh_token(db, user)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ─── LOGOUT ─────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(
    data: LogoutRequest,
    db: Session = Depends(get_db),
):
    """Revoke the given refresh token.

    Deliberately idempotent: an unknown, expired or already-revoked token is
    a no-op and the response never changes, so the endpoint cannot be used to
    probe whether a token was still live. No bearer token is required — a
    caller whose access token has already expired must still be able to log
    out.
    """
    revoke_refresh_token_by_value(db, data.refresh_token)
    db.commit()

    return {"message": "Logged out"}


# ─── CHANGE PASSWORD ────────────────────────────────────────────────────────

@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(
        data.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(data.new_password)

    # Every existing session dies with the old password.
    revoke_user_refresh_tokens(db, current_user.id)

    db.commit()

    # Best effort: the change already happened, so a mail failure must not
    # turn a successful change into an error response.
    background_tasks.add_task(send_password_changed_email, current_user.email)

    return {
        "message": "Password changed successfully",
    }


# ─── FORGOT PASSWORD ────────────────────────────────────────────────────────

@router.post("/forget-password")
def forget_password(
    data: ForgetPasswordRequest,
    db: Session = Depends(get_db),
):
    # Always the same response, whether or not the address is registered:
    # the token is delivered by e-mail and the API must not reveal which
    # addresses have accounts.
    generic_message = (
        "If an account with that email exists, a password reset link has "
        "been sent."
    )

    user = find_user_by_email(db, data.email)

    if user:
        reset_token, jti = create_password_reset_token(user.id)
        store_password_reset_token(user, jti)
        db.commit()
        send_password_reset_email(user.email, reset_token)

    return {"message": generic_message}


# ─── RESET PASSWORD ─────────────────────────────────────────────────────────

@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            data.reset_token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")
        jti = payload.get("jti")
        token_type = payload.get("type")

        if not user_id or token_type != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password reset token",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password reset token"
        )

    # `sub` arrives as text; parse it so the lookup works on every backend
    # and a non-UUID sub is rejected exactly like any other bad token.
    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password reset token",
        )

    user = db.get(User, user_uuid)

    # The token is single-use: it is only accepted while its hashed jti is
    # stored and unexpired, and the stored value is cleared below.
    if not user or not password_reset_token_matches(user, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password reset token",
        )

    user.password_hash = hash_password(data.new_password)
    clear_password_reset_token(user)

    # A reset means the old password (and every session opened with it) is
    # compromised — revoke them all.
    revoke_user_refresh_tokens(db, user.id)

    db.commit()

    background_tasks.add_task(send_password_changed_email, user.email)

    return {
        "message": "Password Reset Successfully"
    }


# ─── GET ME ──────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserDetailsResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.patch(
    "/me",
    response_model=UserDetailsResponse,
)
def update_me(
    data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the caller's full name and/or phone — nothing else.

    `exclude_unset` distinguishes a field the client did not send (leave it
    alone) from an explicit `null` (clear the phone number).
    """
    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(current_user, field, value)

    if updates:
        db.commit()
        db.refresh(current_user)

    return current_user
