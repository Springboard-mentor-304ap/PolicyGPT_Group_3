from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.policy import Policy
from backend.app.models.scheme import Scheme
from backend.app.models.search_history import SearchHistory
from backend.app.models.user import User


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


def get_policy_statistics(db: Session) -> dict:
    category_rows = (
        db.query(Policy.category, func.count(Policy.id))
        .group_by(Policy.category)
        .all()
    )

    status_rows = (
        db.query(Policy.status, func.count(Policy.id))
        .group_by(Policy.status)
        .all()
    )

    department_rows = (
        db.query(Policy.department, func.count(Policy.id))
        .group_by(Policy.department)
        .all()
    )

    return {
        "policies_by_category": {
            category.value: count for category, count in category_rows
        },
        "policies_by_status": {
            status.value: count for status, count in status_rows
        },
        "policies_by_department": {
            department: count for department, count in department_rows
        },
    }