from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user, get_current_user_optional
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.search.schemas import (
    SearchHistoryResponse,
    SearchResponse,
    SearchType,
)
from backend.app.search.service import (
    clear_search_history,
    list_search_history,
    search,
)

# One page of "my searches": the last 50 entries, newest first.
DEFAULT_HISTORY_LIMIT = 50

router = APIRouter(prefix="/search", tags=["Search"])

@router.get("", response_model=SearchResponse)
def search_items(
    query: str | None = Query(default=None),
    search_type: SearchType = Query(default=SearchType.ALL),
    category: str | None = Query(default=None),
    department: str | None = Query(default=None),
    ministry: str | None = Query(default=None),
    state: str | None = Query(default=None),
    page: int = Query(default = 1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    # Expired schemes are hidden from public callers unless asked for.
    include_expired: bool = Query(default=False),
    db: Session = Depends(get_db),
    # Public endpoint: the optional user only narrows an official's results.
    current_user: User | None = Depends(get_current_user_optional),
):
    return search(
        db=db,
        query=query,
        search_type=search_type,
        category=category,
        department=department,
        ministry=ministry,
        state=state,
        page=page,
        page_size=page_size,
        include_expired=include_expired,
        current_user=current_user,
    )


@router.get("/history", response_model=list[SearchHistoryResponse])
def search_history(
    response: Response,
    limit: int = Query(default=DEFAULT_HISTORY_LIMIT, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The caller's own search history, newest first, paged."""
    rows, total = list_search_history(
        db,
        current_user,
        limit=limit,
        offset=offset,
    )

    response.headers["X-Total-Count"] = str(total)

    return rows


@router.delete("/history")
def clear_search_history_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear the caller's own search history (nobody else's)."""
    return {"deleted": clear_search_history(db, current_user)}