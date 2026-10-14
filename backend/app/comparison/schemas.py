from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

class ComparisonType(str, Enum):
    POLICY = "policy"
    SCHEME = "scheme"

class ComparisonRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=4)
    type: ComparisonType

class ComparisonItem(BaseModel):
    id: UUID
    title: str
    description: str
    type: ComparisonType
    category: str
    department: str | None
    ministry: str | None
    state: str | None
    status: str

    # Scheme specific fields
    benefits: list[str] | None = None
    eligibility: list[str] = Field(default_factory=list)
    application_process: str | None = None

    launch_date: str | None = None
    deadline_date: str | None = None
    document_url: str | None = None

class ComparisonResponse(BaseModel):
    items: list[ComparisonItem]