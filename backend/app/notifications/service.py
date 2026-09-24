import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from datetime import datetime, timezone


from backend.app.models.notification import Notification, NotificationChannel, NotificationType
from backend.app.models.user import User

load_dotenv()

def send_email(
    to_email: str,
    subject: str,
    body: str,
) -> None:
    smtp_host = os.getenv("BREVO_SMTP_HOST")
    smtp_port = int(os.getenv("BREVO_SMTP_PORT", "587"))
    smtp_login = os.getenv("BREVO_SMTP_LOGIN")
    smtp_password = os.getenv("BREVO_SMTP_PASSWORD")
    from_email = os.getenv("BREVO_FROM_EMAIL")
    from_name = os.getenv("BREVO_FROM_NAME", "PolicyGPT")

    if not all([
        smtp_host,
        smtp_login,
        smtp_password,
        from_email,
    ]):
        raise RuntimeError("Brevo SMTP configuration is incomplete")

    email = EmailMessage()
    email["From"] = f"{from_name} <{from_email}>"
    email["To"] = to_email
    email["Subject"] = subject
    email.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(smtp_login, smtp_password)
        smtp.send_message(email)

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

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

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

        if channel == NotificationChannel.EMAIL:
            send_email(
                to_email=user.email,
                subject=title,
                body = message,
            )
            notification.sent_at = datetime.now(timezone.utc)

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
    