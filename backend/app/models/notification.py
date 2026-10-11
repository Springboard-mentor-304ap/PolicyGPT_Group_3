from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class NotificationType(str, Enum):
    NEW_POLICY = "new_policy"
    SCHEME_UPDATE = "scheme_update"
    DEADLINE_REMINDER = "deadline_reminder"
    APPLICATION_UPDATE = "application_update"
    # Workflow notifications queued by the transaction that made the change.
    POLICY_REJECTED = "policy_rejected"
    SCHEME_APPROVED = "scheme_approved"
    SCHEME_REJECTED = "scheme_rejected"
    ROLE_REQUEST_UPDATE = "role_request_update"
    FEEDBACK_UPDATE = "feedback_update"
    APPROVAL_PENDING = "approval_pending"
    NEW_APPLICATION = "new_application"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    type: Mapped[NotificationType] = mapped_column(
        SQLEnum(NotificationType, name="notification_type"),
        nullable=False,
    )

    channel: Mapped[NotificationChannel] = mapped_column(
        SQLEnum(NotificationChannel, name="notification_channel"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    related_entity_type: Mapped[str | None] = mapped_column(
        String(50),
    )

    related_entity_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_notifications_user_id_is_read",
            "user_id",
            "is_read",
        ),
    )