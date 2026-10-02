from fastapi import Depends, APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.notifications.schemas import (
    NotificationResponse,
    UnreadCountResponse,
    MarkAllReadResponse,
    MarkReadResponse,
    DeadlineReminderRunResponse,
)
from backend.app.notifications.service import (
    get_unread_count,
    list_notifications,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    run_deadline_reminders,
)

# Reminder sweeps change data for every applicant, so they are restricted to
# platform administrators rather than department-scoped officials.
DEADLINE_REMINDER_RUN_ROLES = (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN)

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)

@router.get(
    "",
    response_model=list[NotificationResponse],
)
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_notifications(db, current_user)


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
)
def get_notification_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
): 
    return UnreadCountResponse(
        unread_count=get_unread_count(db, current_user)
    )


@router.post(
    "/deadline-reminders/run",
    response_model=DeadlineReminderRunResponse,
)
def run_deadline_reminders_route(
    threshold_days: int | None = Query(default=None, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the deadline reminder sweep on demand (administrators only).

    The scheduled in-process sweep uses the same idempotent service function,
    so triggering it here can never create duplicate reminders.
    """
    if current_user.role not in DEADLINE_REMINDER_RUN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can run deadline reminders",
        )

    return run_deadline_reminders(db, threshold_days=threshold_days)


@router.patch("/read-all", response_model=MarkAllReadResponse)
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated_count = mark_all_notifications_as_read(
        db,
        current_user,
    )

    return {"updated_count": updated_count}


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
): 
    return mark_notification_as_read(db, notification_id, current_user)
