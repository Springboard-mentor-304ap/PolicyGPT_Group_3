from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.analytics.schemas import AnalyticsOverview
from backend.app.analytics.service import (
    get_analytics_overview,
    get_policy_statistics,
    get_scheme_statistics,
    get_user_usage_statistics,
    get_department_statistics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


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