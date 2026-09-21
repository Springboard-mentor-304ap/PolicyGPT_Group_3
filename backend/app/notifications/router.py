from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.notifications.schemas import (
    NotificationResponse,
    UnreadCountResponse,
)
from backend.app.notifications.service import (
    get_unread_count,
    list_notifications,
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