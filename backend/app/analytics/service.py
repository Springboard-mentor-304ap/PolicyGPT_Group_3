from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.policy import Policy
from backend.app.models.scheme import Scheme
from backend.app.models.search_history import SearchHistory


def get_analytics_overview(db: Session) -> dict:
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_policies = db.query(func.count(Policy.id)).scalar() or 0
    total_schemes = db.query(func.count(Scheme.id)).scalar() or 0
    total_searches = db.query(func.count(SearchHistory.id)).scalar() or 0

    return {
        "total_users": total_users,
        "total_policies": total_policies,
        "total_schemes": total_schemes,
        "total_searches": total_searches,
    }