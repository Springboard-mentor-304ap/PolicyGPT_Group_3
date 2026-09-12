from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.policy import PolicyCategory, PolicyStatus


class PolicyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    required_documents: list[str] | None = None
    category: PolicyCategory
    department: str = Field(min_length=1, max_length=150)
    ministry: str | None = Field(default=None, max_length=150)
    state: str | None = Field(default=None, max_length=100)
    document_url: str | None = Field(default=None, max_length=500)
    published_date: date | None = None


class PolicyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    required_documents: list[str] | None = None
    category: PolicyCategory | None = None
    department: str | None = Field(default=None, min_length=1, max_length=150)
    ministry: str | None = Field(default=None, max_length=150)
    state: str | None = Field(default=None, max_length=100)
    document_url: str | None = Field(default=None, max_length=500)
    published_date: date | None = None


class PolicyReject(BaseModel):
    rejection_reason: str = Field(min_length=1, max_length=1000)


class PolicyResponse(BaseModel):
    id: UUID
    title: str
    description: str
    required_documents: list[str] | None
    category: PolicyCategory
    department: str
    ministry: str | None
    state: str | None
    status: PolicyStatus
    document_url: str | None
    published_date: date | None
    uploaded_by: UUID
    approved_by: UUID | None
    rejection_reason: str | None
    view_count: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
