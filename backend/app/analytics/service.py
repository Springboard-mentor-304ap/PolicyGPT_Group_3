from datetime import datetime, timedelta, timezone
from typing import Optional, List
from collections import defaultdict

from sqlalchemy import func, desc, or_, and_
from sqlalchemy.orm import Session

from backend.app.models.user import User, UserRole
from backend.app.models.policy import Policy, PolicyStatus, PolicyCategory
from backend.app.models.scheme import Scheme, SchemeStatus, SchemeCategory
from backend.app.models.search_history import SearchHistory
from backend.app.models.audit_log import AuditLog
from backend.app.models.role_request import RoleRequest, RequestedRole, RequestStatus
from backend.app.analytics.schemas import (
    DashboardAnalyticsResponse,
    OverviewMetrics,
    CategoryMetric,
    StatusMetric,
    DepartmentMetric,
    StateMetric,
    SchemeUsageItem,
    SearchIntelligence,
    TopQueryMetric,
    ActivityItem,
    TimeSeriesDataPoint,
)


def _format_label(name: str | None) -> str:
    if not name:
        return "Unknown"
    return name.replace("_", " ").replace("-", " ").title()


def get_user_department(db: Session, user: User) -> Optional[str]:
    """Retrieve the official's authorized department from their approved RoleRequest or uploaded items."""
    # 1. Primary: Approved RoleRequest details
    role_req = (
        db.query(RoleRequest)
        .filter(
            RoleRequest.user_id == user.id,
            RoleRequest.status == RequestStatus.APPROVED,
            RoleRequest.requested_role == RequestedRole.GOVERNMENT_OFFICIAL,
        )
        .order_by(RoleRequest.reviewed_at.desc().nullslast(), RoleRequest.created_at.desc())
        .first()
    )
    if role_req and role_req.details and isinstance(role_req.details, dict):
        dept = role_req.details.get("department_ministry")
        if dept:
            return str(dept).strip()

    # 2. Fallback: Department from policy uploaded by user
    policy = db.query(Policy.department).filter(Policy.uploaded_by == user.id).first()
    if policy and policy[0]:
        return str(policy[0]).strip()

    # 3. Fallback: Department from scheme created by user
    scheme = db.query(Scheme.department).filter(Scheme.created_by == user.id).first()
    if scheme and scheme[0]:
        return str(scheme[0]).strip()

    return None


def get_dashboard_analytics(
    db: Session,
    current_user: Optional[User] = None,
) -> DashboardAnalyticsResponse:
    role = current_user.role if current_user else "guest"
    user_dept: Optional[str] = None

    if current_user and role == UserRole.GOVERNMENT_OFFICIAL:
        user_dept = get_user_department(db, current_user)

    # ── 1. Base Query Filters by Role ──────────────────────────────────────────
    policy_query = db.query(Policy)
    scheme_query = db.query(Scheme)

    if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        # Admins see all non-archived policies & schemes across all users
        policy_query = policy_query.filter(Policy.status != PolicyStatus.ARCHIVED)
        scheme_query = scheme_query.filter(Scheme.status != SchemeStatus.ARCHIVED)

    elif role == UserRole.GOVERNMENT_OFFICIAL:
        # Officials are strictly filtered to their assigned department
        if user_dept:
            policy_query = policy_query.filter(func.lower(Policy.department) == func.lower(user_dept))
            scheme_query = scheme_query.filter(func.lower(Scheme.department) == func.lower(user_dept))
        else:
            # If no department recorded yet, filter by their own uploads
            policy_query = policy_query.filter(Policy.uploaded_by == current_user.id)
            scheme_query = scheme_query.filter(Scheme.created_by == current_user.id)

    else:
        # Citizens, researchers, organizations, guests: Approved policies and active schemes only
        policy_query = policy_query.filter(Policy.status == PolicyStatus.APPROVED)
        scheme_query = scheme_query.filter(Scheme.status == SchemeStatus.ACTIVE)

    # ── 2. Overview Counts ───────────────────────────────────────────────────
    total_policies = policy_query.count()
    total_schemes = scheme_query.count()

    total_users: Optional[int] = None
    total_searches: Optional[int] = None

    if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        total_users = db.query(func.count(User.id)).scalar() or 0
        total_searches = db.query(func.count(SearchHistory.id)).scalar() or 0

    elif role in (UserRole.GOVERNMENT_OFFICIAL, UserRole.RESEARCHER):
        if role == UserRole.GOVERNMENT_OFFICIAL and user_dept:
            # Searches matching department name or department policies
            dept_term = f"%{user_dept}%"
            total_searches = (
                db.query(func.count(SearchHistory.id))
                .filter(SearchHistory.query_text.ilike(dept_term))
                .scalar()
                or 0
            )
            # Fallback if specific department search count is 0: provide platform search activity count
            if total_searches == 0:
                total_searches = db.query(func.count(SearchHistory.id)).scalar() or 0
        else:
            total_searches = db.query(func.count(SearchHistory.id)).scalar() or 0

    overview = OverviewMetrics(
        total_users=total_users,
        total_policies=total_policies,
        total_schemes=total_schemes,
        total_searches=total_searches,
    )

    # ── 3. Policies by Category ──────────────────────────────────────────────
    cat_counts = (
        policy_query.with_entities(Policy.category, func.count(Policy.id))
        .group_by(Policy.category)
        .all()
    )
    policies_by_category: List[CategoryMetric] = []
    for cat, count in cat_counts:
        cat_val = cat.value if hasattr(cat, "value") else str(cat)
        pct = round((count / total_policies * 100), 1) if total_policies > 0 else 0.0
        policies_by_category.append(
            CategoryMetric(
                category=cat_val,
                label=_format_label(cat_val),
                count=count,
                percentage=pct,
            )
        )
    policies_by_category.sort(key=lambda x: x.count, reverse=True)

    # ── 4. Policies by Status (Admins & Gov Officials only) ───────────────────
    policies_by_status: Optional[List[StatusMetric]] = None
    if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN, UserRole.GOVERNMENT_OFFICIAL):
        # Query status counts including all relevant statuses
        if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
            status_query = db.query(Policy.status, func.count(Policy.id)).group_by(Policy.status)
        else:
            if user_dept:
                status_query = (
                    db.query(Policy.status, func.count(Policy.id))
                    .filter(func.lower(Policy.department) == func.lower(user_dept))
                    .group_by(Policy.status)
                )
            else:
                status_query = (
                    db.query(Policy.status, func.count(Policy.id))
                    .filter(Policy.uploaded_by == current_user.id)
                    .group_by(Policy.status)
                )

        status_counts = status_query.all()
        status_total = sum(c for _, c in status_counts) or 1
        policies_by_status = []
        for st, count in status_counts:
            st_val = st.value if hasattr(st, "value") else str(st)
            pct = round((count / status_total * 100), 1)
            policies_by_status.append(
                StatusMetric(
                    status=st_val,
                    label=_format_label(st_val),
                    count=count,
                    percentage=pct,
                )
            )
        policies_by_status.sort(key=lambda x: x.count, reverse=True)

    # ── 5. Policies by Department ────────────────────────────────────────────
    dept_counts = (
        policy_query.with_entities(Policy.department, func.count(Policy.id))
        .filter(Policy.department.isnot(None))
        .group_by(Policy.department)
        .order_by(desc(func.count(Policy.id)))
        .limit(8)
        .all()
    )
    policies_by_department = [
        DepartmentMetric(department=dept or "General", count=count)
        for dept, count in dept_counts
    ]

    # ── 6. Schemes by Category ───────────────────────────────────────────────
    scheme_cat_counts = (
        scheme_query.with_entities(Scheme.category, func.count(Scheme.id))
        .group_by(Scheme.category)
        .all()
    )
    schemes_by_category: List[CategoryMetric] = []
    for cat, count in scheme_cat_counts:
        cat_val = cat.value if hasattr(cat, "value") else str(cat)
        pct = round((count / total_schemes * 100), 1) if total_schemes > 0 else 0.0
        schemes_by_category.append(
            CategoryMetric(
                category=cat_val,
                label=_format_label(cat_val),
                count=count,
                percentage=pct,
            )
        )
    schemes_by_category.sort(key=lambda x: x.count, reverse=True)

    # ── 7. Schemes by Status (Admins & Gov Officials only) ────────────────────
    schemes_by_status: Optional[List[StatusMetric]] = None
    if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN, UserRole.GOVERNMENT_OFFICIAL):
        if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
            s_status_query = db.query(Scheme.status, func.count(Scheme.id)).group_by(Scheme.status)
        else:
            if user_dept:
                s_status_query = (
                    db.query(Scheme.status, func.count(Scheme.id))
                    .filter(func.lower(Scheme.department) == func.lower(user_dept))
                    .group_by(Scheme.status)
                )
            else:
                s_status_query = (
                    db.query(Scheme.status, func.count(Scheme.id))
                    .filter(Scheme.created_by == current_user.id)
                    .group_by(Scheme.status)
                )

        s_status_counts = s_status_query.all()
        s_status_total = sum(c for _, c in s_status_counts) or 1
        schemes_by_status = []
        for st, count in s_status_counts:
            st_val = st.value if hasattr(st, "value") else str(st)
            pct = round((count / s_status_total * 100), 1)
            schemes_by_status.append(
                StatusMetric(
                    status=st_val,
                    label=_format_label(st_val),
                    count=count,
                    percentage=pct,
                )
            )
        schemes_by_status.sort(key=lambda x: x.count, reverse=True)

    # ── 8. Schemes by Department & State ─────────────────────────────────────
    scheme_dept_counts = (
        scheme_query.with_entities(Scheme.department, func.count(Scheme.id))
        .filter(Scheme.department.isnot(None))
        .group_by(Scheme.department)
        .order_by(desc(func.count(Scheme.id)))
        .limit(8)
        .all()
    )
    schemes_by_department = [
        DepartmentMetric(department=dept or "General", count=count)
        for dept, count in scheme_dept_counts
    ]

    scheme_state_counts = (
        scheme_query.with_entities(Scheme.state, func.count(Scheme.id))
        .filter(Scheme.state.isnot(None))
        .group_by(Scheme.state)
        .order_by(desc(func.count(Scheme.id)))
        .limit(8)
        .all()
    )
    schemes_by_state = [
        StateMetric(state=state or "National", count=count)
        for state, count in scheme_state_counts
    ]
    if not schemes_by_state:
        # Default national state badge if null
        schemes_by_state = [StateMetric(state="National", count=total_schemes)]

    # ── 9. Scheme Usage (Top Viewed Schemes) ──────────────────────────────────
    top_viewed_schemes: Optional[List[SchemeUsageItem]] = None
    if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN, UserRole.GOVERNMENT_OFFICIAL, UserRole.RESEARCHER, UserRole.ORGANIZATION):
        top_schemes_query = scheme_query.order_by(Scheme.view_count.desc(), Scheme.created_at.desc()).limit(5)
        top_viewed_schemes = [
            SchemeUsageItem(
                id=str(s.id),
                title=s.title,
                category=s.category.value if hasattr(s.category, "value") else str(s.category),
                department=s.department,
                view_count=s.view_count or 0,
                status=s.status.value if hasattr(s.status, "value") else str(s.status),
            )
            for s in top_schemes_query.all()
        ]

    # ── 10. Search Intelligence (Admins & Researchers) ───────────────────────
    search_intelligence: Optional[SearchIntelligence] = None
    if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN, UserRole.RESEARCHER, UserRole.GOVERNMENT_OFFICIAL):
        top_queries_raw = (
            db.query(SearchHistory.query_text, func.count(SearchHistory.id))
            .filter(SearchHistory.query_text.isnot(None), SearchHistory.query_text != "")
            .group_by(SearchHistory.query_text)
            .order_by(desc(func.count(SearchHistory.id)))
            .limit(6)
            .all()
        )
        top_queries = [
            TopQueryMetric(query=q, count=c)
            for q, c in top_queries_raw
        ]
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_count = (
            db.query(func.count(SearchHistory.id))
            .filter(SearchHistory.searched_at >= seven_days_ago)
            .scalar()
            or 0
        )
        search_intelligence = SearchIntelligence(
            total_searches=total_searches or 0,
            top_queries=top_queries,
            recent_searches_count=recent_count,
        )

    # ── 11. User Activity (Admins & Gov Officials) ───────────────────────────
    user_activity: Optional[List[ActivityItem]] = None
    if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN, UserRole.GOVERNMENT_OFFICIAL):
        act_query = db.query(AuditLog)
        if role == UserRole.GOVERNMENT_OFFICIAL:
            # Scoped to actions by this official or on their department items
            act_query = act_query.filter(AuditLog.actor_id == current_user.id)
        
        recent_logs = act_query.order_by(AuditLog.created_at.desc()).limit(8).all()
        user_activity = []
        for log in recent_logs:
            actor = db.get(User, log.actor_id)
            user_activity.append(
                ActivityItem(
                    id=str(log.id),
                    action=_format_label(log.action),
                    target_table=_format_label(log.target_table),
                    actor_name=actor.full_name if actor else "System User",
                    actor_role=actor.role.value if (actor and hasattr(actor.role, "value")) else "User",
                    created_at=log.created_at.isoformat(),
                    details=f"{_format_label(log.action)} on {_format_label(log.target_table)}",
                )
            )

    # ── 12. Usage Over Time (Admins, Gov Officials, Researchers) ─────────────
    usage_over_time: Optional[List[TimeSeriesDataPoint]] = None
    if role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN, UserRole.RESEARCHER, UserRole.GOVERNMENT_OFFICIAL):
        # Generate daily points for the past 7 days
        today = datetime.now(timezone.utc).date()
        daily_points = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
            day_end = datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc)

            searches_count = (
                db.query(func.count(SearchHistory.id))
                .filter(SearchHistory.searched_at >= day_start, SearchHistory.searched_at <= day_end)
                .scalar()
                or 0
            )

            p_query = db.query(func.count(Policy.id)).filter(
                Policy.created_at >= day_start, Policy.created_at <= day_end
            )
            s_query = db.query(func.count(Scheme.id)).filter(
                Scheme.created_at >= day_start, Scheme.created_at <= day_end
            )

            if role == UserRole.GOVERNMENT_OFFICIAL and user_dept:
                p_query = p_query.filter(func.lower(Policy.department) == func.lower(user_dept))
                s_query = s_query.filter(func.lower(Scheme.department) == func.lower(user_dept))

            p_count = p_query.scalar() or 0
            s_count = s_query.scalar() or 0

            daily_points.append(
                TimeSeriesDataPoint(
                    date=day.strftime("%b %d"),
                    searches=searches_count,
                    policies_created=p_count,
                    schemes_created=s_count,
                )
            )
        usage_over_time = daily_points

    return DashboardAnalyticsResponse(
        user_role=role.value if hasattr(role, "value") else str(role),
        user_department=user_dept,
        overview=overview,
        policies_by_category=policies_by_category,
        policies_by_status=policies_by_status,
        policies_by_department=policies_by_department,
        schemes_by_category=schemes_by_category,
        schemes_by_status=schemes_by_status,
        schemes_by_department=schemes_by_department,
        schemes_by_state=schemes_by_state,
        top_viewed_schemes=top_viewed_schemes,
        search_intelligence=search_intelligence,
        user_activity=user_activity,
        usage_over_time=usage_over_time,
    )
