from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user_optional
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.search.schemas import SearchResponse, SearchType
from backend.app.search.service import  search

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
        current_user=current_user,
    )