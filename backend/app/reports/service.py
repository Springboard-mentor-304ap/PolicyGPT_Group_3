import uuid
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Date, DateTime, cast, func
from sqlalchemy.orm import Session

from backend.app.analytics.service import (
    get_analytics_overview,
    get_department_statistics,
    get_notification_statistics,
    get_policy_statistics,
    get_scheme_statistics,
    get_user_usage_statistics,
)
from backend.app.models.application import Application
from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)
from backend.app.models.notification import Notification
from backend.app.models.policy import Policy, PolicyCategory, PolicyStatus
from backend.app.models.report import Report, ReportFormat, ReportType
from backend.app.models.scheme import Scheme, SchemeCategory, SchemeStatus
from backend.app.models.search_history import SearchHistory
from backend.app.models.user import User, UserRole
from backend.app.reports.generators import format_timestamp
from backend.app.reports.schemas import (
    ReportContent,
    ReportFilters,
    ReportGenerateRequest,
    ReportSection,
    ReportSummaryItem,
    ReportTable,
)

EnumMember = TypeVar("EnumMember", bound=Enum)

# Roles allowed to use the Reports module at all
REPORT_ALLOWED_ROLES = (
    UserRole.GOVERNMENT_OFFICIAL,
    UserRole.ADMINISTRATOR,
    UserRole.SUPER_ADMIN,
)

# Roles whose reports are platform-wide instead of department scoped
REPORT_PLATFORM_ROLES = (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN)

# Calendar-day convention for the whole Reports module.
#
# Report content is printed in UTC and every date filter (date_from/date_to)
# means a UTC calendar day, so the same filter values select the same days for
# every report type. Filter bounds are built as UTC midnight boundaries and
# dated series are bucketed with timezone('UTC', column) instead of relying on
# the database session timezone used by func.date() on its own.
REPORT_TIMEZONE = "UTC"

REPORTS_DIRECTORY = Path(__file__).resolve().parents[2] / "generated_reports"

REPORT_TITLES = {
    ReportType.POLICY: "Policy Report",
    ReportType.SCHEME: "Scheme Report",
    ReportType.USER_ACTIVITY: "User Activity Report",
    ReportType.DEPARTMENT: "Department Report",
    ReportType.ANALYTICS: "Analytics Report",
}

REPORT_FILE_EXTENSIONS = {
    ReportFormat.PDF: "pdf",
    ReportFormat.EXCEL: "xlsx",
}

REPORT_MEDIA_TYPES = {
    ReportFormat.PDF: "application/pdf",
    ReportFormat.EXCEL: (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
}

FILTER_FIELDS = (
    "department",
    "ministry",
    "state",
    "category",
    "status",
    "role",
    "date_from",
    "date_to",
)

# Filters that actually map to real fields for each report type. Anything
# outside this set is rejected instead of being silently ignored.
FILTERS_BY_REPORT_TYPE = {
    ReportType.POLICY: frozenset(
        {
            "department",
            "ministry",
            "state",
            "category",
            "status",
            "date_from",
            "date_to",
        }
    ),
    ReportType.SCHEME: frozenset(
        {
            "department",
            "ministry",
            "state",
            "category",
            "status",
            "date_from",
            "date_to",
        }
    ),
    ReportType.USER_ACTIVITY: frozenset({"role", "date_from", "date_to"}),
    ReportType.DEPARTMENT: frozenset(
        {"department", "ministry", "state", "date_from", "date_to"}
    ),
    ReportType.ANALYTICS: frozenset(),
}


def _require_generator(current_user: User) -> None:
    if current_user.role not in REPORT_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to generate reports",
        )


def _get_department_scope(
    db: Session,
    current_user: User,
) -> str | None:
    """Return the department an official is restricted to.

    Administrators get ``None``, which means platform-wide access. The
    department is read from the authenticated user's official profile so a
    value supplied by the client can never widen the scope.
    """

    if current_user.role in REPORT_PLATFORM_ROLES:
        return None

    scope = (
        db.query(GovernmentOfficialProfile.department)
        .filter(GovernmentOfficialProfile.user_id == current_user.id)
        .scalar()
    )

    if not scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Government official profile is missing",
        )

    return scope


def _pending_filter_names(filters: ReportFilters) -> list[str]:
    return [
        name
        for name in FILTER_FIELDS
        if getattr(filters, name) is not None
    ]


def _validate_filters(
    report_type: ReportType,
    filters: ReportFilters,
) -> None:
    allowed = FILTERS_BY_REPORT_TYPE[report_type]

    unsupported = sorted(
        name
        for name in _pending_filter_names(filters)
        if name not in allowed
    )

    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Filter(s) {', '.join(unsupported)} are not supported for "
                f"{report_type.value} reports"
            ),
        )

    if (
        filters.date_from is not None
        and filters.date_to is not None
        and filters.date_from > filters.date_to
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from cannot be later than date_to",
        )


def _enforce_department_scope(
    filters: ReportFilters,
    scope: str | None,
) -> None:
    """Reject requests whose department filter points outside the scope."""

    if scope is None:
        return

    for field in ("department", "ministry"):
        requested = getattr(filters, field)

        if requested and requested.casefold() != scope.casefold():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You can only generate reports for your own department"
                ),
            )


def _parse_enum_filter(
    value: str | None,
    enum_class: type[EnumMember],
    filter_name: str,
) -> EnumMember | None:
    if value is None:
        return None

    try:
        return enum_class(value)
    except ValueError:
        allowed = ", ".join(member.value for member in enum_class)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid {filter_name} filter. Allowed values: {allowed}"
            ),
        )


def _date_range(
    filters: ReportFilters,
) -> tuple[datetime | None, datetime | None]:
    """Convert filter dates into an inclusive started/ended UTC range."""

    start = None
    end = None

    if filters.date_from is not None:
        start = datetime.combine(
            filters.date_from,
            time.min,
            tzinfo=timezone.utc,
        )

    if filters.date_to is not None:
        end = datetime.combine(
            filters.date_to + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )

    return start, end


def _apply_criteria(query, criteria: list):
    if criteria:
        query = query.filter(*criteria)

    return query


def _apply_date_range(query, column, start, end):
    if start is not None:
        query = query.filter(column >= start)

    if end is not None:
        query = query.filter(column < end)

    return query


def _business_date_column(day_column, fallback_column):
    """UTC timestamp of a record's business date, for date filtering.

    Report date filters used to run against `created_at`, so a policy that was
    published in 2020 only matched the year it happened to be imported in.
    The business date (published date for policies, launch date for schemes)
    is what the report is actually about, so it is used whenever the record
    has one. Records that are not there yet (for example a policy still
    waiting for approval) fall back to their creation day instead of becoming
    invisible to every date range.
    """
    day = func.coalesce(
        day_column,
        cast(func.timezone(REPORT_TIMEZONE, fallback_column), Date),
    )

    return func.timezone(REPORT_TIMEZONE, cast(day, DateTime))


def _format_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _count_rows(counts: dict[str, int]) -> list[list]:
    return [
        [label, count]
        for label, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], str(item[0])),
        )
    ]


def _daily_series(
    db: Session,
    column,
    identifier,
    start: datetime | None,
    end: datetime | None,
) -> list[list]:
    """Daily counts bucketed by UTC calendar day.

    The analytics service buckets its dated series with func.date(), which
    resolves in the database session timezone. Reports use UTC calendar days
    for both filters and dated series, so the bucketing is done explicitly in
    UTC here and the requested date range is applied to the timestamp itself.
    """

    day = func.date(func.timezone(REPORT_TIMEZONE, column))

    query = _apply_date_range(
        db.query(day, func.count(identifier)),
        column,
        start,
        end,
    )

    return [
        [str(day_value), count]
        for day_value, count in query.group_by(day).order_by(day).all()
    ]


def _build_policy_report(
    db: Session,
    filters: ReportFilters,
    scope: str | None,
) -> tuple[list[ReportSummaryItem], list[ReportSection]]:
    category = _parse_enum_filter(
        filters.category,
        PolicyCategory,
        "category",
    )
    policy_status = _parse_enum_filter(
        filters.status,
        PolicyStatus,
        "status",
    )
    start, end = _date_range(filters)

    query = db.query(Policy)

    if scope is not None:
        # Officials are locked to their own department/ministry; a matching
        # filter in the request is confirmed above but never widens the scope.
        query = query.filter(Policy.ministry == scope)
    else:
        if filters.department:
            query = query.filter(Policy.department == filters.department)

        if filters.ministry:
            query = query.filter(Policy.ministry == filters.ministry)

    if filters.state:
        query = query.filter(Policy.state == filters.state)

    if category is not None:
        query = query.filter(Policy.category == category)

    if policy_status is not None:
        query = query.filter(Policy.status == policy_status)

    query = _apply_date_range(
        query,
        _business_date_column(Policy.published_date, Policy.created_at),
        start,
        end,
    )

    policies = query.order_by(Policy.created_at.desc()).all()

    rows = [
        [
            str(policy.id),
            policy.title,
            policy.category.value,
            policy.department,
            policy.ministry,
            policy.state,
            policy.status.value,
            _format_date(policy.published_date),
            policy.view_count,
            format_timestamp(policy.created_at),
        ]
        for policy in policies
    ]

    summary = [
        ReportSummaryItem(
            label="Total Policies",
            value=str(len(policies)),
        ),
        ReportSummaryItem(
            label="Approved Policies",
            value=str(
                sum(
                    1
                    for policy in policies
                    if policy.status == PolicyStatus.APPROVED
                )
            ),
        ),
        ReportSummaryItem(
            label="Total Policy Views",
            value=str(sum(policy.view_count for policy in policies)),
        ),
        ReportSummaryItem(
            label="Departments Covered",
            value=str(len({policy.department for policy in policies})),
        ),
    ]

    sections = [
        ReportSection(
            title="Policies",
            tables=[
                ReportTable(
                    columns=[
                        "Policy ID",
                        "Title",
                        "Category",
                        "Department",
                        "Ministry",
                        "State",
                        "Status",
                        "Published Date",
                        "Views",
                        "Created At",
                    ],
                    rows=rows,
                )
            ],
        )
    ]

    return summary, sections


def _build_scheme_report(
    db: Session,
    filters: ReportFilters,
    scope: str | None,
) -> tuple[list[ReportSummaryItem], list[ReportSection]]:
    category = _parse_enum_filter(
        filters.category,
        SchemeCategory,
        "category",
    )
    scheme_status = _parse_enum_filter(
        filters.status,
        SchemeStatus,
        "status",
    )
    start, end = _date_range(filters)

    query = (
        db.query(Scheme, Policy.title)
        .join(Policy, Scheme.policy_id == Policy.id)
    )

    if scope is not None:
        # Schemes have no ministry of their own, so the department scope is
        # resolved through the parent policy (same rule as Analytics).
        query = query.filter(Policy.ministry == scope)
    elif filters.ministry:
        query = query.filter(Policy.ministry == filters.ministry)

    if scope is None and filters.department:
        query = query.filter(Scheme.department == filters.department)

    if filters.state:
        query = query.filter(Scheme.state == filters.state)

    if category is not None:
        query = query.filter(Scheme.category == category)

    if scheme_status is not None:
        query = query.filter(Scheme.status == scheme_status)

    query = _apply_date_range(
        query,
        _business_date_column(Scheme.launch_date, Scheme.created_at),
        start,
        end,
    )

    schemes = query.order_by(Scheme.created_at.desc()).all()

    today = date.today()

    rows = [
        [
            str(scheme.id),
            scheme.title,
            policy_title,
            scheme.category.value,
            scheme.department,
            scheme.state,
            scheme.status.value,
            _format_date(scheme.launch_date),
            _format_date(scheme.deadline_date),
            scheme.view_count,
            format_timestamp(scheme.created_at),
        ]
        for scheme, policy_title in schemes
    ]

    summary = [
        ReportSummaryItem(
            label="Total Schemes",
            value=str(len(schemes)),
        ),
        ReportSummaryItem(
            label="Active Schemes",
            value=str(
                sum(
                    1
                    for scheme, _ in schemes
                    if scheme.status == SchemeStatus.ACTIVE
                )
            ),
        ),
        ReportSummaryItem(
            label="Schemes Past Deadline",
            value=str(
                sum(
                    1
                    for scheme, _ in schemes
                    if scheme.deadline_date is not None
                    and scheme.deadline_date < today
                )
            ),
        ),
        ReportSummaryItem(
            label="Total Scheme Views",
            value=str(sum(scheme.view_count for scheme, _ in schemes)),
        ),
    ]

    sections = [
        ReportSection(
            title="Schemes",
            tables=[
                ReportTable(
                    columns=[
                        "Scheme ID",
                        "Title",
                        "Policy",
                        "Category",
                        "Department",
                        "State",
                        "Status",
                        "Launch Date",
                        "Deadline Date",
                        "Views",
                        "Created At",
                    ],
                    rows=rows,
                )
            ],
        )
    ]

    return summary, sections


def _build_user_activity_report(
    db: Session,
    filters: ReportFilters,
    scope: str | None,
) -> tuple[list[ReportSummaryItem], list[ReportSection]]:
    if scope is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "User activity reports cover the whole platform and require "
                "administrator access"
            ),
        )

    role = _parse_enum_filter(filters.role, UserRole, "role")

    statistics = get_user_usage_statistics(db)

    all_role_counts = statistics.get("users_by_role", {})
    role_counts = all_role_counts
    table_title = "Users by Role"

    if role is not None:
        role_counts = {
            name: count
            for name, count in all_role_counts.items()
            if name == role.value
        }
        table_title = f"Users by Role (role filter: {role.value})"

    start, end = _date_range(filters)

    registrations = _daily_series(
        db,
        User.created_at,
        User.id,
        start,
        end,
    )
    searches = _daily_series(
        db,
        SearchHistory.searched_at,
        SearchHistory.id,
        start,
        end,
    )

    summary = [
        ReportSummaryItem(
            label="Total Users (all time)",
            value=str(sum(all_role_counts.values())),
        ),
        ReportSummaryItem(
            label="Active Users (all time)",
            value=str(statistics.get("active_users", 0)),
        ),
        ReportSummaryItem(
            label="Inactive Users (all time)",
            value=str(statistics.get("inactive_users", 0)),
        ),
        ReportSummaryItem(
            label="Users Matching Role Filter",
            value=(
                str(sum(role_counts.values()))
                if role is not None
                else "All roles"
            ),
        ),
        ReportSummaryItem(
            label="Registrations in Selected Range",
            value=str(sum(row[1] for row in registrations)),
        ),
        ReportSummaryItem(
            label="Searches in Selected Range",
            value=str(sum(row[1] for row in searches)),
        ),
    ]

    sections = [
        ReportSection(
            title="User Activity",
            tables=[
                ReportTable(
                    title=table_title,
                    columns=["Role", "Users"],
                    rows=_count_rows(role_counts),
                ),
                ReportTable(
                    title="Users by Status (all time)",
                    columns=["Status", "Users"],
                    rows=[
                        ["Active", statistics.get("active_users", 0)],
                        ["Inactive", statistics.get("inactive_users", 0)],
                    ],
                ),
                ReportTable(
                    title="User Registrations Over Time (UTC calendar days)",
                    columns=["Date", "Registrations"],
                    rows=registrations,
                ),
                ReportTable(
                    title="Search Activity Over Time (UTC calendar days)",
                    columns=["Date", "Searches"],
                    rows=searches,
                ),
            ],
        )
    ]

    return summary, sections


def _build_department_report(
    db: Session,
    filters: ReportFilters,
    scope: str | None,
) -> tuple[list[ReportSummaryItem], list[ReportSection]]:
    start, end = _date_range(filters)

    criteria = []

    if scope is not None:
        criteria.append(Policy.ministry == scope)
    else:
        if filters.department:
            criteria.append(Policy.department == filters.department)

        if filters.ministry:
            criteria.append(Policy.ministry == filters.ministry)

    if filters.state:
        criteria.append(Policy.state == filters.state)

    policy_query = _apply_criteria(
        db.query(
            Policy.department,
            Policy.ministry,
            func.count(Policy.id),
        ),
        criteria,
    )
    scheme_query = _apply_criteria(
        db.query(
            Policy.department,
            Policy.ministry,
            func.count(Scheme.id),
        )
        .select_from(Policy)
        .join(Scheme, Scheme.policy_id == Policy.id),
        criteria,
    )
    application_query = _apply_criteria(
        db.query(
            Policy.department,
            Policy.ministry,
            func.count(Application.id),
        )
        .select_from(Policy)
        .join(Scheme, Scheme.policy_id == Policy.id)
        .join(Application, Application.scheme_id == Scheme.id),
        criteria,
    )

    policy_rows = (
        _apply_date_range(
            policy_query,
            _business_date_column(Policy.published_date, Policy.created_at),
            start,
            end,
        )
        .group_by(Policy.department, Policy.ministry)
        .all()
    )
    scheme_rows = (
        _apply_date_range(
            scheme_query,
            _business_date_column(Scheme.launch_date, Scheme.created_at),
            start,
            end,
        )
        .group_by(Policy.department, Policy.ministry)
        .all()
    )
    application_rows = (
        _apply_date_range(
            application_query,
            Application.submitted_at,
            start,
            end,
        )
        .group_by(Policy.department, Policy.ministry)
        .all()
    )

    totals: dict[tuple[str, str | None], dict[str, int]] = {}

    for key, count in ((row[:2], row[2]) for row in policy_rows):
        totals.setdefault(
            key,
            {"policies": 0, "schemes": 0, "applications": 0},
        )["policies"] = count

    for key, count in ((row[:2], row[2]) for row in scheme_rows):
        totals.setdefault(
            key,
            {"policies": 0, "schemes": 0, "applications": 0},
        )["schemes"] = count

    for key, count in ((row[:2], row[2]) for row in application_rows):
        totals.setdefault(
            key,
            {"policies": 0, "schemes": 0, "applications": 0},
        )["applications"] = count

    department_rows = [
        [
            department,
            ministry,
            counts["policies"],
            counts["schemes"],
            counts["applications"],
        ]
        for (department, ministry), counts in sorted(
            totals.items(),
            key=lambda item: (-item[1]["policies"], item[0][0]),
        )
    ]

    official_query = db.query(
        GovernmentOfficialProfile.department,
        func.count(GovernmentOfficialProfile.user_id),
    )

    if scope is not None:
        official_query = official_query.filter(
            GovernmentOfficialProfile.department == scope
        )

    official_rows = (
        official_query
        .group_by(GovernmentOfficialProfile.department)
        .order_by(GovernmentOfficialProfile.department)
        .all()
    )

    summary = [
        ReportSummaryItem(
            label="Departments Covered",
            value=str(len(department_rows)),
        ),
        ReportSummaryItem(
            label="Total Policies",
            value=str(sum(row[2] for row in department_rows)),
        ),
        ReportSummaryItem(
            label="Total Schemes",
            value=str(sum(row[3] for row in department_rows)),
        ),
        ReportSummaryItem(
            label="Total Applications",
            value=str(sum(row[4] for row in department_rows)),
        ),
    ]

    sections = [
        ReportSection(
            title="Departments",
            tables=[
                ReportTable(
                    columns=[
                        "Department",
                        "Ministry",
                        "Policies",
                        "Schemes",
                        "Applications",
                    ],
                    rows=department_rows,
                )
            ],
        ),
        ReportSection(
            title="Government Officials",
            tables=[
                ReportTable(
                    title=(
                        "Government Officials by Department "
                        "(date filters do not apply)"
                    ),
                    columns=["Department", "Officials"],
                    rows=[
                        [department, count]
                        for department, count in official_rows
                    ],
                )
            ],
        ),
    ]

    return summary, sections


def _notification_section(
    db: Session,
    notification_statistics: dict,
) -> ReportSection:
    """Notification aggregates for platform-wide (administrator) reports."""

    return ReportSection(
        title="Notifications",
        tables=[
            ReportTable(
                title="Notifications by Type",
                columns=["Type", "Notifications"],
                rows=_count_rows(
                    notification_statistics.get("notifications_by_type", {})
                ),
            ),
            ReportTable(
                title="Notifications by Channel",
                columns=["Channel", "Notifications"],
                rows=_count_rows(
                    notification_statistics.get(
                        "notifications_by_channel",
                        {},
                    )
                ),
            ),
            ReportTable(
                title="Notifications by Read Status",
                columns=["Status", "Notifications"],
                rows=[
                    ["Read" if label == "true" else "Unread", count]
                    for label, count in _count_rows(
                        notification_statistics.get(
                            "notifications_by_read_status",
                            {},
                        )
                    )
                ],
            ),
            ReportTable(
                title="Notifications Over Time (UTC calendar days)",
                columns=["Date", "Notifications"],
                rows=_daily_series(
                    db,
                    Notification.created_at,
                    Notification.id,
                    None,
                    None,
                ),
            ),
        ],
    )


def _build_analytics_report(
    db: Session,
    filters: ReportFilters,
    scope: str | None,
    current_user: User,
) -> tuple[list[ReportSummaryItem], list[ReportSection]]:
    # Reuse the existing analytics service instead of re-deriving statistics.
    # These helpers already apply the official's own department scope.
    platform_scope = current_user.role in REPORT_PLATFORM_ROLES

    overview = get_analytics_overview(db, current_user)
    policy_statistics = get_policy_statistics(db, current_user)
    scheme_statistics = get_scheme_statistics(db, current_user)
    department_statistics = get_department_statistics(db, current_user)

    # The overview is department scoped for policies and schemes, but
    # total_users and total_searches are calculated platform-wide, so they are
    # only included for platform-wide roles.
    overview_rows = [
        ["Total Policies", overview["total_policies"]],
        ["Total Schemes", overview["total_schemes"]],
    ]

    if platform_scope:
        overview_rows.insert(0, ["Total Users", overview["total_users"]])
        overview_rows.append(
            ["Total Searches", overview["total_searches"]]
        )

    sections = [
        ReportSection(
            title="Overview",
            tables=[
                ReportTable(
                    columns=["Metric", "Value"],
                    rows=overview_rows,
                )
            ],
        ),
        ReportSection(
            title="Policies",
            tables=[
                ReportTable(
                    title="Policies by Category",
                    columns=["Category", "Policies"],
                    rows=_count_rows(
                        policy_statistics.get("policies_by_category", {})
                    ),
                ),
                ReportTable(
                    title="Policies by Status",
                    columns=["Status", "Policies"],
                    rows=_count_rows(
                        policy_statistics.get("policies_by_status", {})
                    ),
                ),
            ],
        ),
        ReportSection(
            title="Schemes",
            tables=[
                ReportTable(
                    title="Schemes by Category",
                    columns=["Category", "Schemes"],
                    rows=_count_rows(
                        scheme_statistics.get("schemes_by_category", {})
                    ),
                ),
                ReportTable(
                    title="Schemes by Status",
                    columns=["Status", "Schemes"],
                    rows=_count_rows(
                        scheme_statistics.get("schemes_by_status", {})
                    ),
                ),
                ReportTable(
                    title="Scheme Usage (by views)",
                    columns=["Scheme ID", "Title", "Views"],
                    rows=[
                        [
                            usage["scheme_id"],
                            usage["title"],
                            usage["view_count"],
                        ]
                        for usage in scheme_statistics.get(
                            "scheme_usage",
                            [],
                        )
                    ],
                ),
            ],
        ),
        ReportSection(
            title="Departments",
            tables=[
                ReportTable(
                    title="Policies by Department",
                    columns=["Department", "Policies"],
                    rows=_count_rows(
                        policy_statistics.get("policies_by_department", {})
                    ),
                ),
                ReportTable(
                    title="Schemes by Department",
                    columns=["Department", "Schemes"],
                    rows=_count_rows(
                        department_statistics.get(
                            "schemes_by_department",
                            {},
                        )
                    ),
                ),
            ],
        ),
    ]

    # Platform-wide user usage statistics stay administrator-only, matching
    # the existing GET /api/analytics/users permission.
    if platform_scope:
        user_statistics = get_user_usage_statistics(db)

        sections.append(
            ReportSection(
                title="Users",
                tables=[
                    ReportTable(
                        title="Users by Role",
                        columns=["Role", "Users"],
                        rows=_count_rows(
                            user_statistics.get("users_by_role", {})
                        ),
                    ),
                    ReportTable(
                        title="Users by Status",
                        columns=["Status", "Users"],
                        rows=[
                            [
                                "Active",
                                user_statistics.get("active_users", 0),
                            ],
                            [
                                "Inactive",
                                user_statistics.get("inactive_users", 0),
                            ],
                        ],
                    ),
                    ReportTable(
                        title="User Registrations Over Time (UTC calendar days)",
                        columns=["Date", "Registrations"],
                        rows=_daily_series(
                            db,
                            User.created_at,
                            User.id,
                            None,
                            None,
                        ),
                    ),
                    ReportTable(
                        title="Search Activity Over Time (UTC calendar days)",
                        columns=["Date", "Searches"],
                        rows=_daily_series(
                            db,
                            SearchHistory.searched_at,
                            SearchHistory.id,
                            None,
                            None,
                        ),
                    ),
                ],
            )
        )

    # Notification aggregates are platform-wide and cannot be scoped to an
    # official's own department, so the section is only present for
    # platform-wide roles.
    if platform_scope:
        sections.append(
            _notification_section(
                db,
                get_notification_statistics(db),
            )
        )

    summary = [
        ReportSummaryItem(
            label="Total Policies",
            value=str(overview["total_policies"]),
        ),
        ReportSummaryItem(
            label="Total Schemes",
            value=str(overview["total_schemes"]),
        ),
    ]

    if platform_scope:
        summary.insert(
            0,
            ReportSummaryItem(
                label="Total Users (all time)",
                value=str(overview["total_users"]),
            ),
        )
        summary.append(
            ReportSummaryItem(
                label="Total Searches (all time)",
                value=str(overview["total_searches"]),
            )
        )

    summary.append(
        ReportSummaryItem(
            label="Department Scope",
            value=scope or "All departments",
        )
    )

    return summary, sections


def _build_report_body(
    db: Session,
    report_type: ReportType,
    filters: ReportFilters,
    scope: str | None,
    current_user: User,
) -> tuple[list[ReportSummaryItem], list[ReportSection]]:
    if report_type == ReportType.POLICY:
        return _build_policy_report(db, filters, scope)

    if report_type == ReportType.SCHEME:
        return _build_scheme_report(db, filters, scope)

    if report_type == ReportType.USER_ACTIVITY:
        return _build_user_activity_report(db, filters, scope)

    if report_type == ReportType.DEPARTMENT:
        return _build_department_report(db, filters, scope)

    return _build_analytics_report(db, filters, scope, current_user)


def _write_report_file(content: ReportContent, file_path: Path) -> None:
    """Write the export file.

    ReportLab and openpyxl are imported here rather than at module scope so
    that a missing or broken reporting dependency cannot stop the rest of the
    API from starting up.
    """

    if content.format == ReportFormat.PDF:
        from backend.app.reports.generators.pdf import generate_pdf_report

        generate_pdf_report(content, file_path)

        return

    from backend.app.reports.generators.excel import generate_excel_report

    generate_excel_report(content, file_path)


def _remove_file(file_path: Path) -> None:
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass


def report_file_path(report_id: UUID, report_format: ReportFormat) -> Path:
    """Files are named after the report UUID, never after user input."""

    extension = REPORT_FILE_EXTENSIONS[report_format]

    return REPORTS_DIRECTORY / f"{report_id}.{extension}"


def generate_report(
    db: Session,
    report_request: ReportGenerateRequest,
    current_user: User,
) -> Report:
    _require_generator(current_user)

    filters = report_request.filters or ReportFilters()
    _validate_filters(report_request.report_type, filters)

    scope = _get_department_scope(db, current_user)
    _enforce_department_scope(filters, scope)

    summary, sections = _build_report_body(
        db,
        report_request.report_type,
        filters,
        scope,
        current_user,
    )

    generated_at = datetime.now(timezone.utc)
    filters_used: dict[str, str] = filters.model_dump(
        exclude_none=True,
        mode="json",
    )

    if scope is not None:
        filters_used["enforced_department_scope"] = scope

    content = ReportContent(
        title=REPORT_TITLES[report_request.report_type],
        report_type=report_request.report_type,
        format=report_request.format,
        generated_at=generated_at,
        generated_by=current_user.full_name,
        filters=filters_used,
        summary=summary,
        sections=sections,
    )

    report_id = uuid.uuid4()
    file_path = report_file_path(report_id, report_request.format)

    # Directory preparation, export and file validation share a single
    # controlled failure path, so a filesystem problem cannot escape as an
    # uncontrolled exception or leave a report row behind.
    try:
        REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
        _write_report_file(content, file_path)

        if not file_path.is_file() or file_path.stat().st_size == 0:
            raise OSError("generated report file is empty")
    except Exception as error:
        _remove_file(file_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report file could not be generated",
        ) from error

    report = Report(
        id=report_id,
        generated_by=current_user.id,
        report_type=report_request.report_type,
        format=report_request.format,
        filters_used=filters_used,
        file_url=f"/api/reports/{report_id}/download",
        generated_at=generated_at,
    )

    try:
        db.add(report)
        db.commit()
        db.refresh(report)
    except Exception as error:
        db.rollback()
        _remove_file(file_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report could not be saved",
        ) from error

    return report


def list_reports(
    db: Session,
    current_user: User,
) -> list[Report]:
    query = db.query(Report)

    # Administrators see the platform-wide history; officials only see the
    # reports they generated themselves.
    if current_user.role not in REPORT_PLATFORM_ROLES:
        query = query.filter(Report.generated_by == current_user.id)

    return query.order_by(Report.generated_at.desc()).all()


def get_report(
    db: Session,
    report_id: UUID,
    current_user: User,
) -> Report:
    report = db.get(Report, report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if (
        current_user.role not in REPORT_PLATFORM_ROLES
        and report.generated_by != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this report",
        )

    return report


def get_report_file(report: Report) -> Path:
    file_path = report_file_path(report.id, report.format)

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated report file is no longer available",
        )

    return file_path


def build_download_filename(report: Report) -> str:
    extension = REPORT_FILE_EXTENSIONS[report.format]

    return (
        f"policygpt_{report.report_type.value}_"
        f"{str(report.id)[:8]}.{extension}"
    )
