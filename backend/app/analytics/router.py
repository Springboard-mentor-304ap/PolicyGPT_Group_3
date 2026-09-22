from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.analytics.schemas import AnalyticsOverview
from backend.app.analytics.service import (
    get_analytics_overview,
    get_policy_statistics,
    get_scheme_statistics,
    get_user_usage_statistics,
    get_department_statistics,
    get_notification_statistics,
)
from backend.app.models.user import User, UserRole


# Roles allowed to access Analytics
ANALYTICS_ALLOWED_ROLES = {
    UserRole.GOVERNMENT_OFFICIAL,
    UserRole.RESEARCHER,
    UserRole.ADMINISTRATOR,
    UserRole.SUPER_ADMIN,
}


# Check whether the logged-in user has permission
def require_analytics_access(
    current_user: User = Depends(get_current_user),
) -> User:

    if current_user.role not in ANALYTICS_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access analytics",
        )

    return current_user


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    dependencies=[Depends(require_analytics_access)],
)


@router.get("/overview", response_model=AnalyticsOverview)
def analytics_overview(db: Session = Depends(get_db)):
    return get_analytics_overview(db)


@router.get("/policies")
def policy_statistics(db: Session = Depends(get_db)):
    return get_policy_statistics(db)


@router.get("/schemes")
def scheme_statistics(db: Session = Depends(get_db)):
    return get_scheme_statistics(db)


@router.get("/users")
def user_usage_statistics(db: Session = Depends(get_db)):
    return get_user_usage_statistics(db)


@router.get("/departments")
def department_statistics(db: Session = Depends(get_db)):
    return get_department_statistics(db)


@router.get("/notifications")
def notification_statistics(db: Session = Depends(get_db)):
    return get_notification_statistics(db)