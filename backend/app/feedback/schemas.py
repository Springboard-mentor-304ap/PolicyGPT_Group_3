from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from backend.app.models.feedback import FeedbackStatus, FeedbackType


class FeedbackCreate(BaseModel):
    type: FeedbackType
    subject: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("subject", "message")
    @classmethod
    def validate_not_blank(cls, value: str, info: ValidationInfo) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{info.field_name} cannot be blank")
        return value


class FeedbackUpdate(BaseModel):
    status: FeedbackStatus | None = None
    resolution_note: str | None = Field(default=None, min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("resolution_note")
    @classmethod
    def validate_resolution_note(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Resolution note cannot be blank")
        return value


class FeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: FeedbackType
    subject: str
    message: str
    status: FeedbackStatus
    resolved_by: UUID | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
