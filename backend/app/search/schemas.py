from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

class SearchType(str, Enum):
    POLICY = "policy"
    SCHEME = "scheme"
    ALL = "all"

class SearchResult(BaseModel):
    id: UUID
    title: str
    description: str
    type: SearchType
    category: str
    department: str | None
    state: str | None
    # Computed from the deadline at response time, never stored: a scheme is
    # expired when its deadline is set and already in the past. Policies have
    # no deadline and are always False.
    is_expired: bool = False
    model_config = ConfigDict(from_attributes=True)


class SearchHistoryResponse(BaseModel):
    """One entry of the caller's own search history (newest first)."""

    id: UUID
    query_text: str | None
    filters: dict | None
    result_count: int | None
    searched_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    page: int
    page_size: int
    total_pages: int

