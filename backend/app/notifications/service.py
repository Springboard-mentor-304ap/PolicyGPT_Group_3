from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID

from backend.app.models.notification import Notification, NotificationChannel, NotificationType
from backend.app.models.user import User

def create_notification(
    db: Session,
    user_id: UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    channel: NotificationChannel = NotificationChannel.IN_APP,
    related_entity_type: str | None = None,
    related_entity_id: UUID | None = None,    
) -> Notification:
    notification = Notification(
        user_id = user_id,
        type = notification_type,
        channel = channel,
        title = title,
        message = message,
        related_entity_type = related_entity_type,
        related_entity_id = related_entity_id,
    )

    db.add(notification)

    return notification

def get_notification_channels(
    notification_type: NotificationType,
) -> list[NotificationChannel]:
    if notification_type in {
        NotificationType.NEW_POLICY,
        NotificationType.SCHEME_UPDATE,
    }:
        return [NotificationChannel.IN_APP]

    if notification_type == NotificationType.APPLICATION_UPDATE:
        return [
            NotificationChannel.IN_APP,
            NotificationChannel.EMAIL,
        ]

    if notification_type == NotificationType.DEADLINE_REMINDER:
        return [
            NotificationChannel.IN_APP,
            NotificationChannel.EMAIL,
            NotificationChannel.SMS,
        ]

    return [NotificationChannel.IN_APP]

def send_notification(
    db: Session,
    user_id: UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    related_entity_type: str | None = None,
    related_entity_id: UUID | None = None,
) -> list[Notification]:

    channels = get_notification_channels(notification_type)

    notifications = []

    for channel in channels:
        notification = create_notification(
            db=db,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            channel=channel,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )

        notifications.append(notification)

    return notifications

def list_notifications(
    db: Session,
    current_user: User
) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )

def get_unread_count(
        db: Session,
        current_user: User
) -> int:
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .count()
    )

def mark_notification_as_read(
        db: Session,
        notification_id,
        current_user: User,
) -> Notification:
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    notification.is_read = True
    db.commit()
    db.refresh(notification)

    return notification

def mark_all_notifications_as_read(
    db: Session,
    current_user: User,
) -> int:
    updated_count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .update(
            {Notification.is_read: True},
            synchronize_session=False,
        )
    ) 
    db.commit()

    return updated_count
    