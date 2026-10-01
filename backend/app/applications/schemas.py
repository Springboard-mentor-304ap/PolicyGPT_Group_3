from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from backend.app.models.application import ApplicationStatus

class ApplicationCreate(BaseModel):
    scheme_id: UUID

class ApplicationResponse(BaseModel):
    id: UUID
    user_id: UUID
    scheme_id: UUID
    status: ApplicationStatus
    remarks: str | None
    approved_by: UUID | None
    rejection_reason: str | None
    submitted_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    remarks: str | None = None


class ApplicationReviewResponse(ApplicationResponse):
    """Application enriched with review context for the staff list view.

    Extends the existing ApplicationResponse with joined applicant/scheme
    information already present in the database — no new applicant fields.
    """

    applicant_name: str | None = None
    scheme_title: str
    scheme_department: str | None = None
    policy_ministry: str | None = None

    
