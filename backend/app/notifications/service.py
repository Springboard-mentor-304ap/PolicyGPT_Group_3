import logging
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from datetime import date, datetime, timedelta, timezone


from backend.app.models.notification import Notification, NotificationChannel, NotificationType
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.user import User, UserRole

load_dotenv()

logger = logging.getLogger(__name__)

# Roles that can actually submit an application for a scheme. Deadline
# reminders therefore go to the same audience (see create_application).
DEADLINE_REMINDER_ROLES = (
    UserRole.CITIZEN,
    UserRole.ORGANIZATION,
)

# How close a scheme deadline has to be before reminders are generated.
DEADLINE_REMINDER_DEFAULT_THRESHOLD_DAYS = 7

def reminder_threshold_days() -> int:
    raw_value = os.getenv("DEADLINE_REMINDER_THRESHOLD_DAYS")

    if raw_value is None:
        return DEADLINE_REMINDER_DEFAULT_THRESHOLD_DAYS

    try:
        return max(1, int(raw_value))
    except ValueError:
        return DEADLINE_REMINDER_DEFAULT_THRESHOLD_DAYS

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
            # A delivery problem (missing SMTP configuration, provider
            # outage, bad recipient) must not discard the notification rows
            # that were created for the other channels, and must not break
            # batch jobs such as the deadline reminder run.
            try:
                send_email(
                    to_email=user.email,
                    subject=title,
                    body = message,
                )
            except Exception:
                logger.warning(
                    "Email notification %s for %s could not be sent",
                    notification_type.value,
                    user.email,
                    exc_info=True,
                )
            else:
                notification.sent_at = datetime.now(timezone.utc)

        # SMS rows are persisted as records only: no SMS provider is
        # configured, so `sent_at` stays NULL and the record represents a
        # pending/simulated SMS rather than a delivered message.
        notifications.append(notification)

    return notifications# ─── In-app inbox helpers ──────────────────────────────────────────────────
#
# EMAIL and SMS rows are delivery records, not inbox entries: one
# APPLICATION_UPDATE generates an IN_APP and an EMAIL row, and showing both
# made the bell look like it contained duplicate notifications. The API below
# therefore exposes IN_APP records only, and read/unread state (which is what
# the UI and the unread badge reason about) is tracked on those records.

def _in_app_records(db: Session, user_id: UUID):
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.channel == NotificationChannel.IN_APP,
    )


def list_notifications(
    db: Session,
    current_user: User
) -> list[Notification]:
    return (
        _in_app_records(db, current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


def get_unread_count(
        db: Session,
        current_user: User
) -> int:
    return (
        _in_app_records(db, current_user.id)
        .filter(Notification.is_read.is_(False))
        .count()
    )


def mark_notification_as_read(
        db: Session,
        notification_id,
        current_user: User,
) -> Notification:
    notification = _in_app_records(db, current_user.id).filter(
        Notification.id == notification_id,
    ).first()

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
        _in_app_records(db, current_user.id)
        .filter(Notification.is_read.is_(False))
        .update(
            {Notification.is_read: True},
            synchronize_session=False,
        )
    ) 
    db.commit()

    return updated_count


def run_deadline_reminders(
    db: Session,
    threshold_days: int | None = None,
) -> dict:
    """Create DEADLINE_REMINDER notifications for schemes closing soon.

    Reminders go to the users who can actually apply (active citizens and
    organizations) for every ACTIVE scheme whose deadline falls inside the
    reminder window. The run is idempotent: a user is only ever notified once
    per scheme, so repeated executions (scheduled ticks, manual triggers, or
    several API workers) cannot duplicate a reminder.
    """

    if threshold_days is None:
        threshold_days = reminder_threshold_days()

    today = date.today()
    window_end = today + timedelta(days=threshold_days)

    schemes = (
        db.query(Scheme)
        .filter(
            Scheme.status == SchemeStatus.ACTIVE,
            Scheme.deadline_date.is_not(None),
            Scheme.deadline_date >= today,
            Scheme.deadline_date <= window_end,
        )
        .order_by(Scheme.deadline_date.asc())
        .all()
    )

    recipients = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            User.role.in_(DEADLINE_REMINDER_ROLES),
        )
        .all()
    )

    created = 0
    skipped = 0

    for scheme in schemes:
        days_remaining = (scheme.deadline_date - today).days
        title = "Deadline Reminder"
        message = (
            f'The deadline for "{scheme.title}" is approaching.\n'
            f"Deadline: {scheme.deadline_date.isoformat()}\n"
            f"Days remaining: {days_remaining}\n"
            "Please complete your application before the deadline."
        )

        for recipient in recipients:
            already_notified = (
                db.query(Notification.id)
                .filter(
                    Notification.user_id == recipient.id,
                    Notification.type == NotificationType.DEADLINE_REMINDER,
                    Notification.related_entity_type == "scheme",
                    Notification.related_entity_id == scheme.id,
                )
                .first()
            )

            if already_notified:
                skipped += 1
                continue

            send_notification(
                db=db,
                user_id=recipient.id,
                notification_type=NotificationType.DEADLINE_REMINDER,
                title=title,
                message=message,
                related_entity_type="scheme",
                related_entity_id=scheme.id,
            )
            created += 1

    db.commit()

    return {
        "threshold_days": threshold_days,
        "schemes_considered": len(schemes),
        "recipients_considered": len(recipients),
        "reminders_created": created,
        "reminders_skipped": skipped,
    }
    