from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.feedback.schemas import FeedbackCreate, FeedbackUpdate
from backend.app.models.feedback import Feedback, FeedbackStatus, FeedbackType
from backend.app.models.user import User, UserRole


# Roles allowed to view and resolve feedback submitted by other users
FEEDBACK_ADMIN_ROLES = (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN)

# Allowed status transitions for the resolution workflow
ALLOWED_STATUS_TRANSITIONS = frozenset(
    {
        (FeedbackStatus.OPEN, FeedbackStatus.IN_PROGRESS),
        (FeedbackStatus.OPEN, FeedbackStatus.RESOLVED),
        (FeedbackStatus.IN_PROGRESS, FeedbackStatus.RESOLVED),
    }
)


def _load_feedback(
    db: Session,
    feedback_id: UUID,
) -> Feedback:
    feedback = db.get(Feedback, feedback_id)

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )

    return feedback


def create_feedback(
    db: Session,
    feedback_data: FeedbackCreate,
    current_user: User,
) -> Feedback:
    feedback = Feedback(
        user_id=current_user.id,
        type=feedback_data.type,
        subject=feedback_data.subject,
        message=feedback_data.message,
        status=FeedbackStatus.OPEN,
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return feedback


def list_feedback(
    db: Session,
    current_user: User,
    feedback_type: FeedbackType | None = None,
    feedback_status: FeedbackStatus | None = None,
) -> list[Feedback]:
    if current_user.role not in FEEDBACK_ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view all feedback",
        )

    query = db.query(Feedback)

    if feedback_type is not None:
        query = query.filter(Feedback.type == feedback_type)

    if feedback_status is not None:
        query = query.filter(Feedback.status == feedback_status)

    return query.order_by(Feedback.created_at.desc()).all()


def list_my_feedback(
    db: Session,
    current_user: User,
) -> list[Feedback]:
    return (
        db.query(Feedback)
        .filter(Feedback.user_id == current_user.id)
        .order_by(Feedback.created_at.desc())
        .all()
    )


def get_feedback(
    db: Session,
    feedback_id: UUID,
    current_user: User,
) -> Feedback:
    feedback = _load_feedback(db, feedback_id)

    if (
        feedback.user_id != current_user.id
        and current_user.role not in FEEDBACK_ADMIN_ROLES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this feedback",
        )

    return feedback


def update_feedback(
    db: Session,
    feedback_id: UUID,
    feedback_data: FeedbackUpdate,
    current_user: User,
) -> Feedback:
    if current_user.role not in FEEDBACK_ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update feedback status or resolution",
        )

    feedback = _load_feedback(db, feedback_id)

    update_data = feedback_data.model_dump(exclude_unset=True)
    new_status = update_data.get("status")
    new_note = update_data.get("resolution_note")

    if new_status is None and new_note is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported fields were provided for update",
        )

    if new_status is not None and new_status != feedback.status:
        if (feedback.status, new_status) not in ALLOWED_STATUS_TRANSITIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot change feedback status from "
                    f"{feedback.status.value} to {new_status.value}"
                ),
            )

        if new_status == FeedbackStatus.RESOLVED:
            resolution_note = (
                new_note if new_note is not None else feedback.resolution_note
            )

            if resolution_note is None or not resolution_note.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="resolution_note is required when resolving feedback",
                )

            feedback.resolution_note = resolution_note
            feedback.resolved_by = current_user.id
        else:
            # OPEN -> IN_PROGRESS: item is being worked on, not yet resolved
            if new_note is not None:
                feedback.resolution_note = new_note
            feedback.resolved_by = None

        feedback.status = new_status
    elif new_note is not None:
        if feedback.status == FeedbackStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "resolution_note can only be added once feedback is "
                    "in progress or resolved"
                ),
            )

        feedback.resolution_note = new_note

    db.commit()
    db.refresh(feedback)

    return feedback
