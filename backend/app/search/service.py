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
        statement = statement.filter(Policy.ministry == scope)

    if query:
        search_term = f"%{query}%"

        statement = statement.filter(
            or_(
                Policy.title.ilike(search_term),
                Policy.description.ilike(search_term),
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
            Policy.department.ilike(department)
        )

    if ministry:
        statement = statement.filter(
            Policy.ministry.ilike(ministry)
        )

    if state:
        statement = statement.filter(
            Policy.state.ilike(state)
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
        state: str | None = None,
        scope: str | None = None,
) -> list[SearchResult]:

    statement = db.query(Scheme).filter(
        Scheme.status == SchemeStatus.ACTIVE
    )

    if scope:
        statement = statement.filter(
            or_(
                Scheme.department == scope,
                Scheme.policy_id.in_(
                    db.query(Policy.id).filter(Policy.ministry == scope)
                ),
            )
        )

    if query: 
        search_term = f"%{query}%"

        statement = statement.filter(
            or_(
                Scheme.title.ilike(search_term),
                Scheme.description.ilike(search_term),
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
            Scheme.department.ilike(department)
        )

    if state:
        statement = statement.filter(
            Scheme.state.ilike(state)
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
            state=state,
            scope=scope,
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
            state=state,
            scope=scope,
        )

        results = policy_results + scheme_results

    total = len(results)

    # Log search query to search_history if a query or filter was provided
    if query or category or department or state:
        try:
            filters_dict = {}
            if category:
                filters_dict["category"] = category
            if department:
                filters_dict["department"] = department
            if state:
                filters_dict["state"] = state
            
            history_entry = SearchHistory(
                query_text=query.strip() if query else (category or department or state),
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