import secrets
from fastapi import APIRouter, Depends, HTTPException, status
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
)
from backend.app.auth.security import (
    ALGORITHM,
    SECRET_KEY,
    create_password_reset_token,
    create_access_token,
    create_refresh_token,
    create_email_verification_token,
    hash_password,
    verify_password,
)
from backend.app.db.database import get_db
from backend.app.models.user import User, UserRole


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ─── REGISTER ────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    verification_token = create_email_verification_token(data.email)

    user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=UserRole.CITIZEN,
        is_active=True,
        email_verified=False,
        email_verification_token=verification_token,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Dev mode: print verification token to console
    print(f"\n\n{'='*60}")
    print(f"  EMAIL VERIFICATION TOKEN for {data.email}:")
    print(f"  {verification_token}")
    print(f"{'='*60}\n\n")

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


# ─── EMAIL VERIFICATION ─────────────────────────────────────────────────────

@router.post("/verify-email")
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            data.token,
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

    user = db.query(User).filter(User.email == email).first()
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
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # Don't reveal whether email exists
        return {"message": "If the email is registered, a verification link has been sent"}

    if user.email_verified:
        return {"message": "Email already verified"}

    verification_token = create_email_verification_token(user.email)
    user.email_verification_token = verification_token
    db.commit()

    return {
        "message": "Verification email sent",
        "verification_token": verification_token,  # In production, send via email
    }


# ─── LOGIN ───────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

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
    user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found",
        )

    reset_token = create_password_reset_token({
        "sub": str(user.id),
    })

    return {
        "message": "Password reset token generated",
        "reset_token": reset_token,
    }


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
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User Not Found",
        )

    user.password_hash = hash_password(data.new_password)

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
