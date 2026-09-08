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
    model_config = ConfigDict(from_attributes=True)

class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    page: int
    page_size: int
    total_pages: int

