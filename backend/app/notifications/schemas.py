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