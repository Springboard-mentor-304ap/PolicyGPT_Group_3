from sqlalchemy.orm import Session

from backend.app.models.notification import Notification
from backend.app.models.user import User

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