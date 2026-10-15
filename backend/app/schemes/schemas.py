from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from backend.app.dates import utc_today

from backend.app.models.scheme import SchemeCategory, SchemeStatus
from backend.app.models.eligibility_rule import (
    EligibilityParameter,
    EligibilityOperator,
)

class SchemeCreate(BaseModel):
    policy_id: UUID
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    required_documents: list[str] | None = None
    category: SchemeCategory
    benefits: list[str] | None = None
    application_process: str | None = None
    department: str | None = Field(default=None, max_length=150)
    state: str | None = Field(default=None, max_length=100)
    launch_date: date | None = None
    deadline_date: date | None = None
    document_url: str | None = Field(default=None, max_length=500)


class SchemeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    required_documents: list[str] | None = None
    category: SchemeCategory | None = None
    benefits: list[str] | None = None
    application_process: str | None = None
    department: str | None = Field(default=None, max_length=150)
    state: str | None = Field(default=None, max_length=100)
    launch_date: date | None = None
    deadline_date: date | None = None
    document_url: str | None = Field(default=None, max_length=500)


class SchemeReject(BaseModel):
    rejection_reason: str = Field(min_length=1, max_length=1000)


class SchemeResponse(BaseModel):
    id: UUID
    policy_id: UUID
    title: str
    description: str
    required_documents: list[str] | None
    category: SchemeCategory
    benefits: list[str] | None
    application_process: str | None
    department: str | None
    state: str | None
    status: SchemeStatus
    launch_date: date | None
    deadline_date: date | None
    document_url: str | None
    created_by: UUID
    approved_by: UUID | None = None
    rejection_reason: str | None = None
    view_count: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Computed, never stored: the deadline is set and already past.

        The database status is left alone — an expired scheme is still ACTIVE
        (or whatever it was), its application window has simply closed.
        """
        # UTC today, shared with the application cutoff — host-local time
        # must not shift the expiry boundary.
        return self.deadline_date is not None and self.deadline_date < utc_today()


class EligibilityRuleCreate(BaseModel):
    parameter: EligibilityParameter
    operator: EligibilityOperator
    value: str = Field(min_length=1, max_length=255)


class EligibilityRuleUpdate(BaseModel):
    parameter: EligibilityParameter | None = None
    operator: EligibilityOperator | None = None
    value: str | None = Field(default=None, min_length=1, max_length=255)


class EligibilityRuleResponse(BaseModel):
    id: UUID
    scheme_id: UUID
    parameter: EligibilityParameter
    operator: EligibilityOperator
    value: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
