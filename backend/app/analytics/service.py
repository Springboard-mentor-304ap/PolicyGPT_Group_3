from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.policy import Policy
from backend.app.models.scheme import Scheme
from backend.app.models.search_history import SearchHistory
from backend.app.models.user import User
from backend.app.models.notification import Notification


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
def get_scheme_statistics(db: Session) -> dict:
    category_rows = (
        db.query(Scheme.category, func.count(Scheme.id))
        .group_by(Scheme.category)
        .all()
    )

    status_rows = (
        db.query(Scheme.status, func.count(Scheme.id))
        .group_by(Scheme.status)
        .all()
    )

    usage_rows = (
        db.query(
            Scheme.id,
            Scheme.title,
            Scheme.view_count,
        )
        .order_by(Scheme.view_count.desc())
        .all()
    )

    return {
        "schemes_by_category": {
            category.value: count for category, count in category_rows
        },
        "schemes_by_status": {
            status.value: count for status, count in status_rows
        },
        "scheme_usage": [
            {
                "scheme_id": str(scheme_id),
                "title": title,
                "view_count": view_count,
            }
            for scheme_id, title, view_count in usage_rows
        ],
    }
def get_user_usage_statistics(db: Session) -> dict:
    # Users by role
    role_rows = (
        db.query(User.role, func.count(User.id))
        .group_by(User.role)
        .all()
    )

    # Active and inactive users
    active_users = (
        db.query(func.count(User.id))
        .filter(User.is_active.is_(True))
        .scalar()
        or 0
    )

    inactive_users = (
        db.query(func.count(User.id))
        .filter(User.is_active.is_(False))
        .scalar()
        or 0
    )

    # User registrations over time
    registration_rows = (
        db.query(
            func.date(User.created_at).label("date"),
            func.count(User.id),
        )
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
        .all()
    )

    # Searches over time
    search_rows = (
        db.query(
            func.date(SearchHistory.searched_at).label("date"),
            func.count(SearchHistory.id),
        )
        .group_by(func.date(SearchHistory.searched_at))
        .order_by(func.date(SearchHistory.searched_at))
        .all()
    )

    total_searches = (
        db.query(func.count(SearchHistory.id)).scalar()
        or 0
    )

    return {
        "users_by_role": {
            role.value: count for role, count in role_rows
        },
        "active_users": active_users,
        "inactive_users": inactive_users,
        "user_registrations_over_time": [
            {
                "date": str(date),
                "count": count,
            }
            for date, count in registration_rows
        ],
        "total_searches": total_searches,
        "searches_over_time": [
            {
                "date": str(date),
                "count": count,
            }
            for date, count in search_rows
        ],
    }
def get_department_statistics(db: Session) -> dict:
    policy_rows = (
        db.query(
            Policy.department,
            func.count(Policy.id),
        )
        .group_by(Policy.department)
        .all()
    )

    scheme_rows = (
        db.query(
            Scheme.department,
            func.count(Scheme.id),
        )
        .group_by(Scheme.department)
        .all()
    )

    return {
        "policies_by_department": {
            department: count
            for department, count in policy_rows
        },
        "schemes_by_department": {
            department: count
            for department, count in scheme_rows
        },
    }
def get_notification_statistics(db: Session) -> dict:
    type_rows = (
        db.query(
            Notification.type,
            func.count(Notification.id),
        )
        .group_by(Notification.type)
        .all()
    )

    channel_rows = (
        db.query(
            Notification.channel,
            func.count(Notification.id),
        )
        .group_by(Notification.channel)
        .all()
    )

    read_rows = (
        db.query(
            Notification.is_read,
            func.count(Notification.id),
        )
        .group_by(Notification.is_read)
        .all()
    )

    notification_rows = (
        db.query(
            func.date(Notification.created_at).label("date"),
            func.count(Notification.id),
        )
        .group_by(func.date(Notification.created_at))
        .order_by(func.date(Notification.created_at))
        .all()
    )

    return {
        "notifications_by_type": {
            notification_type.value: count
            for notification_type, count in type_rows
        },
        "notifications_by_channel": {
            channel.value: count
            for channel, count in channel_rows
        },
        "notifications_by_read_status": {
            str(is_read).lower(): count
            for is_read, count in read_rows
        },
        "notifications_over_time": [
            {
                "date": str(date),
                "count": count,
            }
            for date, count in notification_rows
        ],
    }