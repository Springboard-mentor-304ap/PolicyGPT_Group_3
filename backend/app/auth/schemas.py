from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from backend.app.models.user_profile import (
    Gender,
    MaritalStatus,
    SocialCategory,
)

# ─── Password policy ─────────────────────────────────────────────────────────

PASSWORD_MIN_LENGTH = 8


def validate_password_strength(value: str) -> str:
    """Shared password policy for register, change and reset.

    Every way a password can be set goes through this check so the policy
    cannot drift between endpoints.
    """
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )

    if not any(character.isalpha() for character in value):
        raise ValueError("Password must contain at least one letter")

    if not any(character.isdigit() for character in value):
        raise ValueError("Password must contain at least one digit")

    return value


# ─── Auth Schemas ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1)
    email: EmailStr
    password: str

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be empty")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        return validate_password_strength(value)

class RegistrationResponse(BaseModel):
    message: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value):
        return validate_password_strength(value)


class ForgetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value):
        return validate_password_strength(value)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class VerifyEmailRequest(BaseModel):
    # Address the code was sent to (the code itself is stored hashed).
    email: EmailStr | None = None
    # 6-digit code from the verification e-mail (current flow).
    code: str | None = None
    # Legacy direct-link token; still accepted so previously issued links keep
    # working.
    token: str | None = None


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# ─── User Response ───────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    phone: str | None = None
    role: str
    is_active: bool
    email_verified: bool

class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    date_of_birth: date | None = None
    gender: Gender | None = None
    marital_status: MaritalStatus | None = None
    religion: str | None = None
    occupation: str | None = None
    annual_income: Decimal | None = None
    social_category: SocialCategory | None = None
    disability_status: bool
    education: str | None = None
    state: str | None = None
    district: str | None = None
    created_at: datetime
    updated_at: datetime


class UserDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    phone: str | None = None
    role: str
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    profile: UserProfileResponse | None = None

# ─── Citizen Profile ─────────────────────────────────────────────────────────

class CitizenProfileRequest(BaseModel):
    phone: str | None = None
    date_of_birth: str | None = None  # ISO date string
    gender: str | None = None
    occupation: str | None = None
    annual_income: float | None = None
    social_category: str | None = None
    disability_status: bool = False
    education: str | None = None
    state: str | None = None
    district: str | None = None


class CitizenProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    phone: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    occupation: str | None = None
    annual_income: float | None = None
    social_category: str | None = None
    disability_status: bool = False
    education: str | None = None
    state: str | None = None
    district: str | None = None


class GovernmentOfficialProfileResponse(BaseModel):
    """Read-only view of a government official's profile.

    The official fields come straight from `government_official_profiles`
    (populated when a role request is approved) and the identity fields from
    the linked user account. No field is editable through the API.
    """

    user_id: UUID
    full_name: str
    email: str
    phone: str | None = None
    department: str
    designation: str
    official_id: str
    state: str
    district: str | None = None


# ─── Role Request ────────────────────────────────────────────────────────────

class RoleRequestSubmit(BaseModel):
    requested_role: str  # researcher, organization, government_official, administrator
    details: dict  # Role-specific form data


class RoleRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    requested_role: str
    status: str
    details: dict | None = None
    review_reason: str | None = None
    reviewer_id: UUID | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class RoleRequestReview(BaseModel):
    review_reason: str | None = None


class MessageResponse(BaseModel):
    message: str
