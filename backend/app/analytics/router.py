from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from backend.app.auth.security import SECRET_KEY, ALGORITHM
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.analytics.schemas import DashboardAnalyticsResponse
from backend.app.analytics.service import get_dashboard_analytics

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)

optional_bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        user_id = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    user = db.get(User, user_id)
    if user and user.is_active:
        return user
    return None


@router.get("/dashboard", response_model=DashboardAnalyticsResponse)
def get_dashboard_analytics_route(
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    return get_dashboard_analytics(db=db, current_user=current_user)
