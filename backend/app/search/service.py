from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.policy import Policy, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.search_history import SearchHistory
from backend.app.models.user import User, UserRole
from backend.app.search.schemas import SearchResult, SearchType
# Reuses the existing department-scope rule the rest of the platform applies
# to government officials (profile department, 403 when it is missing).
from backend.app.analytics.service import _get_official_ministry
# One canonical scope rule (case-insensitive, trimmed, ministry first with
# department fallback) shared with policies, schemes, applications, analytics
# and reports — see backend/app/scope.py.
from backend.app.scope import policy_scope_filter, scheme_scope_filter
from backend.app.pagination import clamp_limit

# Escape character handed to every ILIKE so the user's own %, _ and \ are
# literals instead of wildcards (SQL standard: ESCAPE '\').
LIKE_ESCAPE = "\\"

# Roles that use search as a public discovery surface: for them an expired
# scheme stays hidden unless include_expired is asked for. Staff roles (who
# manage and review those schemes) are never filtered.
PUBLIC_SEARCH_ROLES = frozenset({
    UserRole.CITIZEN,
    UserRole.RESEARCHER,
    UserRole.ORGANIZATION,
})


def _hides_expired(current_user: User | None) -> bool:
    """True when the caller must not see expired schemes by default.

    Guests count as public — search is the open discovery surface.
    """
    return current_user is None or current_user.role in PUBLIC_SEARCH_ROLES


def _escape_like(value: str) -> str:
    """Escape the characters that have meaning inside an ILIKE pattern."""
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _contains_pattern(value: str) -> str:
    """`%value%` with the value's own wildcards escaped."""
    return f"%{_escape_like(value)}%"


def _search_scope(db: Session, current_user: User | None) -> str | None:
    """Department/ministry a government official is limited to.

    Guests, citizens and researchers are unrestricted: search is the public
    discovery surface and approved policies / active schemes are public. An
    official only ever searches inside their own scope.
    """
    if current_user is None or current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        return None

    return _get_official_ministry(db, current_user)


def search_policies(
        db: Session,
        query: str | None = None,
        category: str | None = None,
        department: str | None = None,
        ministry: str | None = None,
        state: str | None = None,
        scope: str | None = None,
) -> list[SearchResult]:

    statement = db.query(Policy).filter(
        Policy.status == PolicyStatus.APPROVED
    )

    if scope:
        statement = statement.filter(policy_scope_filter(scope))

    if query:
        search_term = _contains_pattern(query)

        statement = statement.filter(
            or_(
                Policy.title.ilike(search_term, escape=LIKE_ESCAPE),
                Policy.description.ilike(search_term, escape=LIKE_ESCAPE),
            )
        )

    if category:
        # Only filter by category if it's a valid PolicyCategory
        from backend.app.models.policy import PolicyCategory
        try:
            PolicyCategory(category)
            statement = statement.filter(
                Policy.category == category
            )
        except ValueError:
            # Invalid policy category — skip filter, return no results
            return []

    if department: 
        statement = statement.filter(
            Policy.department.ilike(
                _escape_like(department), escape=LIKE_ESCAPE
            )
        )

    if ministry:
        statement = statement.filter(
            Policy.ministry.ilike(
                _escape_like(ministry), escape=LIKE_ESCAPE
            )
        )

    if state:
        statement = statement.filter(
            Policy.state.ilike(
                _escape_like(state), escape=LIKE_ESCAPE
            )
        )

    policies = statement.all()

    return [
        SearchResult(
            id=policy.id,
            title=policy.title,
            description=policy.description,
            type=SearchType.POLICY,
            category=policy.category.value,
            department=policy.department,
            state=policy.state,
        )
        for policy in policies
    ]

def search_schemes(
        db: Session,
        query: str | None = None,
        category: str | None = None,
        department: str | None = None,
        ministry: str | None = None,
        state: str | None = None,
        scope: str | None = None,
        include_expired: bool = False,
        current_user: User | None = None,
) -> list[SearchResult]:

    statement = db.query(Scheme).filter(
        Scheme.status == SchemeStatus.ACTIVE
    )

    if scope:
        statement = statement.filter(scheme_scope_filter(scope))

    # A scheme whose deadline has passed keeps its status in the database but
    # drops out of public results until include_expired asks for it.
    if not include_expired and _hides_expired(current_user):
        statement = statement.filter(
            or_(
                Scheme.deadline_date.is_(None),
                Scheme.deadline_date >= date.today(),
            )
        )

    if query: 
        search_term = _contains_pattern(query)

        statement = statement.filter(
            or_(
                Scheme.title.ilike(search_term, escape=LIKE_ESCAPE),
                Scheme.description.ilike(search_term, escape=LIKE_ESCAPE),
            )
        )

    if category:
        # Only filter by category if it's a valid SchemeCategory
        from backend.app.models.scheme import SchemeCategory
        try:
            SchemeCategory(category)
            statement = statement.filter(
                Scheme.category == category
            )
        except ValueError:
            # Invalid scheme category — skip filter, return no results
            return []

    if department: 
        statement = statement.filter(
            Scheme.department.ilike(
                _escape_like(department), escape=LIKE_ESCAPE
            )
        )

    # A scheme has no ministry of its own, so the ministry filter is applied
    # through the parent policy (the same field the scope rule uses).
    if ministry:
        statement = statement.filter(
            Scheme.policy_id.in_(
                db.query(Policy.id).filter(
                    Policy.ministry.ilike(
                        _escape_like(ministry), escape=LIKE_ESCAPE
                    )
                )
            )
        )

    if state:
        statement = statement.filter(
            Scheme.state.ilike(
                _escape_like(state), escape=LIKE_ESCAPE
            )
        )

    schemes = statement.all()

    return [
        SearchResult(
            id=scheme.id,
            title=scheme.title,
            description=scheme.description,
            type=SearchType.SCHEME,
            category=scheme.category.value,
            department=scheme.department,
            state=scheme.state,
            is_expired=(
                scheme.deadline_date is not None
                and scheme.deadline_date < date.today()
            ),
        )
        for scheme in schemes
    ]

def search(
        db: Session,
        query: str | None = None,
        search_type: SearchType = SearchType.ALL,
        category: str | None = None,
        department: str | None = None,
        ministry: str | None = None,
        state: str | None = None,
        page: int = 1,
        page_size: int = 10,
        include_expired: bool = False,
        current_user: User | None = None,
):
    if page < 1:
        page = 1

    if page_size < 1:
        page_size = 10

    scope = _search_scope(db, current_user)

    if search_type == SearchType.POLICY:
        results = search_policies(
            db=db,
            query=query,
            category=category,
            department=department,
            ministry=ministry,
            state=state,
            scope=scope,
        )

    elif search_type == SearchType.SCHEME:
        results = search_schemes(
            db=db,
            query=query,
            category=category,
            department=department,
            ministry=ministry,
            state=state,
            scope=scope,
            include_expired=include_expired,
            current_user=current_user,
        )

    else: 
        policy_results = search_policies(
            db=db,
            query=query,
            category=category,
            department=department,
            ministry=ministry,
            state=state,
            scope=scope,
        )

        scheme_results = search_schemes(
            db=db,
            query=query,
            category=category,
            department=department,
            ministry=ministry,
            state=state,
            scope=scope,
            include_expired=include_expired,
            current_user=current_user,
        )

        results = policy_results + scheme_results

    total = len(results)

    # Log the query to search_history: only the first page (the rest are
    # pagination of the same search) and with the caller attached when they
    # are logged in, so analytics can tell users apart from guests.
    if page == 1 and (query or category or department or ministry or state):
        try:
            filters_dict = {}
            if category:
                filters_dict["category"] = category
            if department:
                filters_dict["department"] = department
            if ministry:
                filters_dict["ministry"] = ministry
            if state:
                filters_dict["state"] = state

            history_entry = SearchHistory(
                user_id=current_user.id if current_user is not None else None,
                query_text=query.strip() if query else (category or department or ministry or state),
                filters=filters_dict if filters_dict else None,
                result_count=total,
            )
            db.add(history_entry)
            db.commit()
        except Exception:
            db.rollback()

    start = (page - 1) * page_size
    end = start + page_size

    paginated_results = results[start:end]

    total_pages = (total + page_size -1) // page_size

    return {
        "results": paginated_results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


# ─── Search history ─────────────────────────────────────────────────────────

def list_search_history(
        db: Session,
        current_user: User,
        limit: int = 50,
        offset: int = 0,
) -> tuple[list[SearchHistory], int]:
    """The caller's own searches, newest first, paged.

    Only rows carrying this user's id are returned — history is per account,
    never shared. Returns ``(rows, total)`` for the X-Total-Count header.
    """
    query = db.query(SearchHistory).filter(
        SearchHistory.user_id == current_user.id,
    )

    total = query.count()

    rows = (
        query.order_by(
            SearchHistory.searched_at.desc(),
            SearchHistory.id.desc(),
        )
        .offset(offset)
        .limit(clamp_limit(limit))
        .all()
    )

    return rows, total


def clear_search_history(
        db: Session,
        current_user: User,
) -> int:
    """Delete every history row of the caller and return how many went."""
    deleted = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .delete(synchronize_session=False)
    )

    db.commit()

    return deleted
