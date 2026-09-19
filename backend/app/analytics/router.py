from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.analytics.schemas import AnalyticsOverview
from backend.app.analytics.service import get_analytics_overview


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


@router.get("/overview", response_model=AnalyticsOverview)
def analytics_overview(db: Session = Depends(get_db)):
    return get_analytics_overview(db)