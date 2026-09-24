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

    
