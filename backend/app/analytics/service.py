from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.models.policy import Policy
from backend.app.models.scheme import Scheme
from backend.app.models.search_history import SearchHistory
from backend.app.models.user import User, UserRole
from backend.app.models.notification import Notification
from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)


def _get_official_ministry(
    db: Session,
    current_user: User,
) -> str | None:
    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        return None

    ministry = (
        db.query(GovernmentOfficialProfile.department)
        .filter(
            GovernmentOfficialProfile.user_id == current_user.id
        )
        .scalar()
    )

    if not ministry:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Government official profile is missing",
        )

    return ministry


def get_analytics_overview(
    db: Session,
    current_user: User,
) -> dict:
    ministry = _get_official_ministry(db, current_user)

    # `total_users` and `total_searches` are platform-wide numbers that cannot
    # be scoped to a ministry, so they are only exposed to administrators.
    # Every other analytics role receives None (the API returns null).
    is_platform_admin = current_user.role in (
        UserRole.ADMINISTRATOR,
        UserRole.SUPER_ADMIN,
    )

    total_users = (
        db.query(func.count(User.id)).scalar() or 0
    ) if is_platform_admin else None

    policy_query = db.query(func.count(Policy.id))

    if ministry:
        policy_query = policy_query.filter(
            Policy.ministry == ministry
        )

    total_policies = policy_query.scalar() or 0

    scheme_query = (
        db.query(func.count(Scheme.id))
        .join(Policy, Scheme.policy_id == Policy.id)
    )

    if ministry:
        scheme_query = scheme_query.filter(
            Policy.ministry == ministry
        )

    total_schemes = scheme_query.scalar() or 0

    total_searches = (
        db.query(func.count(SearchHistory.id)).scalar() or 0
    ) if is_platform_admin else None

    return {
        "total_users": total_users,
        "total_policies": total_policies,
        "total_schemes": total_schemes,
        "total_searches": total_searches,
    }


def get_policy_statistics(
    db: Session,
    current_user: User,
) -> dict:
    ministry = _get_official_ministry(db, current_user)

    category_query = (
        db.query(
            Policy.category,
            func.count(Policy.id),
        )
        .group_by(Policy.category)
    )

    if ministry:
        category_query = category_query.filter(
            Policy.ministry == ministry
        )

    category_rows = category_query.all()

    status_query = (
        db.query(
            Policy.status,
            func.count(Policy.id),
        )
        .group_by(Policy.status)
    )

    if ministry:
        status_query = status_query.filter(
            Policy.ministry == ministry
        )

    status_rows = status_query.all()

    department_query = (
        db.query(
            Policy.department,
            func.count(Policy.id),
        )
        .group_by(Policy.department)
    )

    if ministry:
        department_query = department_query.filter(
            Policy.ministry == ministry
        )

    department_rows = department_query.all()

    return {
        "policies_by_category": {
            category.value: count
            for category, count in category_rows
        },
        "policies_by_status": {
            status.value: count
            for status, count in status_rows
        },
        "policies_by_department": {
            department: count
            for department, count in department_rows
        },
    }


def get_scheme_statistics(
    db: Session,
    current_user: User,
) -> dict:
    ministry = _get_official_ministry(db, current_user)

    category_query = (
        db.query(
            Scheme.category,
            func.count(Scheme.id),
        )
        .join(Policy, Scheme.policy_id == Policy.id)
        .group_by(Scheme.category)
    )

    if ministry:
        category_query = category_query.filter(
            Policy.ministry == ministry
        )

    category_rows = category_query.all()

    status_query = (
        db.query(
            Scheme.status,
            func.count(Scheme.id),
        )
        .join(Policy, Scheme.policy_id == Policy.id)
        .group_by(Scheme.status)
    )

    if ministry:
        status_query = status_query.filter(
            Policy.ministry == ministry
        )

    status_rows = status_query.all()

    usage_query = (
        db.query(
            Scheme.id,
            Scheme.title,
            Scheme.view_count,
        )
        .join(Policy, Scheme.policy_id == Policy.id)
    )

    if ministry:
        usage_query = usage_query.filter(
            Policy.ministry == ministry
        )

    usage_rows = (
        usage_query
        .order_by(Scheme.view_count.desc())
        .all()
    )

    return {
        "schemes_by_category": {
            category.value: count
            for category, count in category_rows
        },
        "schemes_by_status": {
            status.value: count
            for status, count in status_rows
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
    role_rows = (
        db.query(User.role, func.count(User.id))
        .group_by(User.role)
        .all()
    )

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

    registration_rows = (
        db.query(
            func.date(User.created_at).label("date"),
            func.count(User.id),
        )
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
        .all()
    )

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
            role.value: count
            for role, count in role_rows
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


def get_department_statistics(
    db: Session,
    current_user: User,
) -> dict:
    ministry = _get_official_ministry(db, current_user)

    policy_query = (
        db.query(
            Policy.department,
            func.count(Policy.id),
        )
        .group_by(Policy.department)
    )

    if ministry:
        policy_query = policy_query.filter(
            Policy.ministry == ministry
        )

    policy_rows = policy_query.all()

    scheme_query = (
        db.query(
            Policy.department,
            func.count(Scheme.id),
        )
        .join(Policy, Scheme.policy_id == Policy.id)
        .group_by(Policy.department)
    )

    if ministry:
        scheme_query = scheme_query.filter(
            Policy.ministry == ministry
        )

    scheme_rows = scheme_query.all()

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