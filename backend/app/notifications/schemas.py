from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from backend.app.models.notification import NotificationChannel, NotificationType

class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: NotificationType
    channel: NotificationChannel
    title: str
    message: str
    related_entity_type: str | None
    related_entity_id: UUID | None
    is_read: bool
    sent_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UnreadCountResponse(BaseModel):
    unread_count: int

class MarkAllReadResponse(BaseModel):
    updated_count: int

class MarkReadResponse(NotificationResponse):
    pass

class DeadlineReminderRunResponse(BaseModel):
    """Result of one deadline-reminder sweep (idempotent per user/scheme)."""

    threshold_days: int
    schemes_considered: int
    recipients_considered: int
    reminders_created: int
    reminders_skipped: int