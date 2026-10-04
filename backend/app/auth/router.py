import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from jose import JWTError, jwt

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.schemas import (
    ChangePasswordRequest,
    ForgetPasswordRequest,
    ResetPasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    VerifyEmailRequest,
    ResendVerificationRequest,
    UserResponse,
    UserDetailsResponse,
    RegistrationResponse
)
from backend.app.auth.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
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
    VerificationCodeError,
    generate_verification_code,
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
    """Verify the 6-digit code against the stored hash and expiry."""
    submitted = code.strip()

    if not submitted.isdigit() or len(submitted) != CODE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    user = find_user_by_email(db, email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    if user.email_verified:
        return {"message": "Email already verified"}

    try:
        code_is_valid = verification_code_matches(user, submitted)
    except VerificationCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    if not code_is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    user.email_verified = True
    user.email_verification_token = None
    db.commit()

    return {"message": "Email verified successfully"}


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

    refresh_token = create_refresh_token({
        "sub": str(user.id),
        "role": user.role.value,
    })

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
    refresh_token: str,
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            refresh_token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")
        token_type = payload.get("type")

        if not user_id or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.get(User, user_id)

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

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
    })

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ─── CHANGE PASSWORD ────────────────────────────────────────────────────────

@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
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

    db.commit()

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

    user = db.get(User, user_id)

    # The token is single-use: it is only accepted while its hashed jti is
    # stored and unexpired, and the stored value is cleared below.
    if not user or not password_reset_token_matches(user, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password reset token",
        )

    user.password_hash = hash_password(data.new_password)
    clear_password_reset_token(user)

    db.commit()

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
