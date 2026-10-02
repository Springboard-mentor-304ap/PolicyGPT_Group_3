from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.schemas import (
    CitizenProfileRequest,
    CitizenProfileResponse,
    GovernmentOfficialProfileResponse,
    MessageResponse,
)
from backend.app.db.database import get_db
from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)
from backend.app.models.user import User, UserRole
from backend.app.models.user_profile import UserProfile

router = APIRouter(
    prefix="/profile",
    tags=["Profile"],
)


def _parse_date(date_str: str | None) -> date | None:
    """Parse ISO date string to date object."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        )


# ─── GET CITIZEN PROFILE ───────────────────────────────────────────────────

@router.get(
    "/citizen",
    response_model=CitizenProfileResponse,
)
def get_citizen_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()

    if not profile:
        # Return empty profile
        return CitizenProfileResponse(
            user_id=current_user.id,
        )

    return CitizenProfileResponse(
        user_id=profile.user_id,
        phone=current_user.phone,
        date_of_birth=profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        gender=profile.gender.value if profile.gender else None,
        occupation=profile.occupation,
        annual_income=float(profile.annual_income) if profile.annual_income else None,
        social_category=profile.social_category.value if profile.social_category else None,
        disability_status=profile.disability_status,
        education=profile.education,
        state=profile.state,
        district=profile.district,
    )


# ─── GET GOVERNMENT OFFICIAL PROFILE ───────────────────────────────────────

@router.get(
    "/government-official",
    response_model=GovernmentOfficialProfileResponse,
)
def get_government_official_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read-only official profile (department, designation, official ID...).

    Returns 404 when the account has no government profile yet — the profile
    is created when an administrator approves a government-official role
    request, so there is nothing the user could fill in from here.
    """
    profile = db.query(GovernmentOfficialProfile).filter(
        GovernmentOfficialProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No government official profile is linked to this account",
        )

    return GovernmentOfficialProfileResponse(
        user_id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        department=profile.department,
        designation=profile.designation,
        official_id=profile.official_id,
        state=profile.state,
        district=profile.district,
    )


# ─── CREATE/UPDATE CITIZEN PROFILE ─────────────────────────────────────────

@router.put(
    "/citizen",
    response_model=CitizenProfileResponse,
)
def update_citizen_profile(
    data: CitizenProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Update phone on User model
    if data.phone is not None:
        current_user.phone = data.phone

    # Get or create profile
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()

    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)

    # Update profile fields
    if data.date_of_birth is not None:
        profile.date_of_birth = _parse_date(data.date_of_birth)

    if data.gender is not None:
        from backend.app.models.user_profile import Gender
        profile.gender = Gender(data.gender)

    if data.occupation is not None:
        profile.occupation = data.occupation

    if data.annual_income is not None:
        from decimal import Decimal
        profile.annual_income = Decimal(str(data.annual_income))

    if data.social_category is not None:
        from backend.app.models.user_profile import SocialCategory
        profile.social_category = SocialCategory(data.social_category)

    profile.disability_status = data.disability_status

    if data.education is not None:
        profile.education = data.education

    if data.state is not None:
        profile.state = data.state

    if data.district is not None:
        profile.district = data.district

    db.commit()
    db.refresh(profile)
    db.refresh(current_user)

    return CitizenProfileResponse(
        user_id=profile.user_id,
        phone=current_user.phone,
        date_of_birth=profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        gender=profile.gender.value if profile.gender else None,
        occupation=profile.occupation,
        annual_income=float(profile.annual_income) if profile.annual_income else None,
        social_category=profile.social_category.value if profile.social_category else None,
        disability_status=profile.disability_status,
        education=profile.education,
        state=profile.state,
        district=profile.district,
    )
