import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Iterable
from dotenv import load_dotenv

from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from datetime import date, datetime, timedelta, timezone


from backend.app.models.application import Application
from backend.app.models.notification import Notification, NotificationChannel, NotificationType
from backend.app.pagination import DEFAULT_LIMIT, clamp_limit
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
    if notification_type in WORKFLOW_NOTIFICATION_TYPES:
        return [NotificationChannel.IN_APP]

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


# Workflow notifications (policy/scheme review, role requests, feedback and
# new applications) are in-app only: no mail or SMS provider is wired for
# them, so an extra channel row would be a record that never leaves the box.
WORKFLOW_NOTIFICATION_TYPES = frozenset(
    {
        NotificationType.POLICY_REJECTED,
        NotificationType.SCHEME_APPROVED,
        NotificationType.SCHEME_REJECTED,
        NotificationType.ROLE_REQUEST_UPDATE,
        NotificationType.FEEDBACK_UPDATE,
        NotificationType.APPROVAL_PENDING,
        NotificationType.NEW_APPLICATION,
    }
)


def queue_notifications(
    db: Session,
    user_ids: Iterable[UUID],
    notification_type: NotificationType,
    title: str,
    message: str,
    related_entity_type: str | None = None,
    related_entity_id: UUID | None = None,
) -> list[Notification]:
    """Stage one IN_APP notification per recipient in the open transaction.

    Nothing is committed here: the caller's commit publishes the change and
    its notifications together, so they succeed or fail as one unit. Rows are
    staged through the session flush, not `bulk_insert_mappings`, because the
    test harness (and any caller sharing a session) must see them before the
    commit.
    """

    notifications = []

    for user_id in user_ids:
        notifications.append(
            create_notification(
                db=db,
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                channel=NotificationChannel.IN_APP,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            )
        )

    return notifications


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
    current_user: User,
    unread_only: bool = False,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[Notification], int]:
    """The caller's in-app inbox, newest first, paged.

    Returns ``(rows, total)`` where `total` counts every matching row before
    paging, which is what the X-Total-Count header carries.
    """
    query = _in_app_records(db, current_user.id)

    if unread_only:
        query = query.filter(Notification.is_read.is_(False))

    total = query.count()

    rows = (
        query.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(clamp_limit(limit))
        .all()
    )

    return rows, total


def delete_notification(
    db: Session,
    notification_id,
    current_user: User,
) -> None:
    """Delete one of the caller's own in-app notifications.

    Delivery records (EMAIL / SMS rows) and other people's notifications are
    invisible here — `_in_app_records` already scopes the lookup — so a wrong
    id is a plain 404.
    """
    notification = _in_app_records(db, current_user.id).filter(
        Notification.id == notification_id,
    ).first()

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    db.delete(notification)
    db.commit()


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
    reminder window — but never to a user who already has an application for
    that scheme. The run is idempotent: a user is only ever notified once per
    scheme, so repeated executions (scheduled ticks, manual triggers, or
    several API workers) cannot duplicate a reminder.

    The "already reminded" and "already applied" lookups are each one bulk
    query for the whole run instead of a query per user per scheme.
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

    scheme_ids = [scheme.id for scheme in schemes]

    # One query for every reminder that already exists for these schemes …
    already_notified = {
        (user_id, entity_id)
        for user_id, entity_id in db.query(
            Notification.user_id,
            Notification.related_entity_id,
        )
        .filter(
            Notification.type == NotificationType.DEADLINE_REMINDER,
            Notification.related_entity_type == "scheme",
            Notification.related_entity_id.in_(scheme_ids),
        )
        .all()
    }

    # … and one query for every user who already applied to them. Applicants
    # have nothing left to do, so they must not be reminded again.
    applicants = {
        (user_id, applied_scheme_id)
        for user_id, applied_scheme_id in db.query(
            Application.user_id,
            Application.scheme_id,
        )
        .filter(Application.scheme_id.in_(scheme_ids))
        .all()
    }

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
            key = (recipient.id, scheme.id)

            if key in applicants:
                skipped += 1
                continue

            if key in already_notified:
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
    