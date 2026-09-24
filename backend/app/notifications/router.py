from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session
from uuid import UUID

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.notifications.schemas import (
    NotificationResponse,
    UnreadCountResponse,
    MarkAllReadResponse,
    MarkReadResponse,
)
from backend.app.notifications.service import (
    get_unread_count,
    list_notifications,
    mark_notification_as_read,
    mark_all_notifications_as_read,
)

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
