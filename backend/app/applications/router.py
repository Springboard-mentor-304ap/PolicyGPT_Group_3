from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.applications.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationReviewResponse,
    ApplicationStatusUpdate,
)
from backend.app.applications.service import (
    create_application,
    get_application,
    list_applications_for_review,
    list_my_applications,
    update_application_status,
)
from backend.app.db.database import get_db
from backend.app.models.application import ApplicationStatus
from backend.app.models.user import User
from backend.app.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/applications",
    tags=["Applications"],
)


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_application(
    data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_application(
        db=db,
        scheme_id=data.scheme_id,
        current_user=current_user,
    )


@router.get(
    "",
    response_model=list[ApplicationResponse],
)
def get_my_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_my_applications(
        db=db,
        current_user=current_user,
    )


# Staff review list — must be registered before "/{application_id}" so the
# literal path is not captured by the UUID parameter route.
@router.get(
    "/review",
    response_model=list[ApplicationReviewResponse],
)
def review_applications(
    application_status: ApplicationStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_applications_for_review(
        db=db,
        status_filter=application_status,
        current_user=current_user,
    )


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
)
def get_application_details(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_application(
        db=db,
        application_id=application_id,
        current_user=current_user,
    )


@router.patch(
    "/{application_id}/status",
    response_model=ApplicationResponse,
)
def change_application_status(
    application_id: UUID,
    data: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_application_status(
        db=db,
        application_id=application_id,
        new_status=data.status,
        remarks=data.remarks,
        current_user=current_user,
    )