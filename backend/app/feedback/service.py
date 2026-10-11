from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.audit.service import client_ip, log_action
from backend.app.feedback.schemas import FeedbackCreate, FeedbackUpdate
from backend.app.models.feedback import Feedback, FeedbackStatus, FeedbackType
from backend.app.models.notification import NotificationType
from backend.app.models.user import User, UserRole
from backend.app.notifications.service import queue_notifications
from backend.app.pagination import DEFAULT_LIMIT, clamp_limit


# Audit log action recorded when feedback moves through the workflow.
AUDIT_FEEDBACK_STATUS_CHANGE = "feedback.status_change"


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
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[Feedback], int]:
    """All feedback the admins may see, newest first, paged.

    Returns ``(rows, total)`` — `total` counts every matching row before
    LIMIT/OFFSET, for the X-Total-Count header.
    """
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

    total = query.count()

    rows = (
        query.order_by(Feedback.created_at.desc())
        .offset(offset)
        .limit(clamp_limit(limit))
        .all()
    )

    return rows, total


def list_my_feedback(
    db: Session,
    current_user: User,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[Feedback], int]:
    query = (
        db.query(Feedback)
        .filter(Feedback.user_id == current_user.id)
    )

    total = query.count()

    rows = (
        query.order_by(Feedback.created_at.desc())
        .offset(offset)
        .limit(clamp_limit(limit))
        .all()
    )

    return rows, total


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
    request: Request | None = None,
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

    old_status = feedback.status
    status_changed = False

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
        status_changed = True
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

    if status_changed:
        # In-app only, queued in the same transaction as the status change.
        # The submitter is never the actor here (only admins may update), but
        # the guard keeps "never notify the actor" true if that ever changes.
        if feedback.user_id != current_user.id:
            message = (
                f'Your feedback "{feedback.subject}" is now '
                f"{feedback.status.value.replace('_', ' ')}."
            )

            if feedback.status == FeedbackStatus.RESOLVED and feedback.resolution_note:
                message += f"\nResolution: {feedback.resolution_note}"

            queue_notifications(
                db=db,
                user_ids=[feedback.user_id],
                notification_type=NotificationType.FEEDBACK_UPDATE,
                title="Feedback Update",
                message=message,
                related_entity_type="feedback",
                related_entity_id=feedback.id,
            )

        log_action(
            db=db,
            actor_id=current_user.id,
            action=AUDIT_FEEDBACK_STATUS_CHANGE,
            target_table="feedback",
            target_id=feedback.id,
            changes={
                "status": {"old": old_status.value, "new": feedback.status.value}
            },
            ip_address=client_ip(request),
        )

    db.commit()
    db.refresh(feedback)

    return feedback
