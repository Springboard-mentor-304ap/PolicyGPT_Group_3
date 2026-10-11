from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.feedback.schemas import (
    FeedbackCreate,
    FeedbackResponse,
    FeedbackUpdate,
)
from backend.app.feedback.service import (
    create_feedback,
    get_feedback,
    list_feedback,
    list_my_feedback,
    update_feedback,
)
from backend.app.models.feedback import FeedbackStatus, FeedbackType
from backend.app.models.user import User
from backend.app.pagination import DEFAULT_LIMIT

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"],
)


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_feedback_route(
    feedback_data: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_feedback(
        db=db,
        feedback_data=feedback_data,
        current_user=current_user,
    )


@router.get(
    "",
    response_model=list[FeedbackResponse],
)
def list_feedback_route(
    response: Response,
    feedback_type: FeedbackType | None = Query(default=None, alias="type"),
    feedback_status: FeedbackStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows, total = list_feedback(
        db=db,
        current_user=current_user,
        feedback_type=feedback_type,
        feedback_status=feedback_status,
        limit=limit,
        offset=offset,
    )

    response.headers["X-Total-Count"] = str(total)

    return rows


@router.get(
    "/my",
    response_model=list[FeedbackResponse],
)
def list_my_feedback_route(
    response: Response,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows, total = list_my_feedback(
        db=db,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )

    response.headers["X-Total-Count"] = str(total)

    return rows


@router.get(
    "/{feedback_id}",
    response_model=FeedbackResponse,
)
def get_feedback_route(
    feedback_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_feedback(
        db=db,
        feedback_id=feedback_id,
        current_user=current_user,
    )


@router.patch(
    "/{feedback_id}",
    response_model=FeedbackResponse,
)
def update_feedback_route(
    feedback_id: UUID,
    feedback_data: FeedbackUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_feedback(
        db=db,
        feedback_id=feedback_id,
        feedback_data=feedback_data,
        current_user=current_user,
        request=request,
    )
