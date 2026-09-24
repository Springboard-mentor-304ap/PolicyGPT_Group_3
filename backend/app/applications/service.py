from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.application import Application, ApplicationStatus
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.user import User, UserRole
from backend.app.models.notification import NotificationType
from backend.app.notifications.service import send_notification

ALLOWED_STATUS_TRANSITIONS = {
    ApplicationStatus.SUBMITTED: {
        ApplicationStatus.UNDER_REVIEW,
    },
    ApplicationStatus.UNDER_REVIEW: {
        ApplicationStatus.ADDITIONAL_INFORMATION_REQUIRED,
        ApplicationStatus.APPROVED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.ADDITIONAL_INFORMATION_REQUIRED: {
        ApplicationStatus.UNDER_REVIEW,
    },
    ApplicationStatus.APPROVED: set(),
    ApplicationStatus.REJECTED: set(),
}

def create_application(
    db: Session,
    scheme_id: UUID,
    current_user: User,
) -> Application:
    if current_user.role not in {
        UserRole.CITIZEN,
        UserRole.ORGANIZATION,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only citizens and organizations can submit applications",
        )

    scheme = (
        db.query(Scheme)
        .filter(Scheme.id == scheme_id)
        .first()
    )

    if not scheme: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheme not found",
        )

    if scheme.status != SchemeStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application can only be submitted for active schemes",
        )

    existing_application = (
        db.query(Application)
        .filter(
            Application.user_id == current_user.id,
            Application.scheme_id == scheme_id,
        )
        .first()
    )

    if existing_application:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already applied for this scheme",
        )

    application = Application(
        user_id = current_user.id,
        scheme_id = scheme_id,
        status = ApplicationStatus.SUBMITTED,
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    return application

def get_application(
        db: Session,
        application_id: UUID,
        current_user: User,
) -> Application: 
    application = (
        db.query(Application)
        .filter(Application.id == application_id)
        .first()
    )

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    if (
        application.user_id != current_user.id
        and current_user.role
        not in {
            UserRole.GOVERNMENT_OFFICIAL,
            UserRole.ADMINISTRATOR,
            UserRole.SUPER_ADMIN,
        }
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view this application",
        )

    return application

def list_my_applications(
    db: Session,
    current_user: User,
) -> list[Application]:
    return (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.submitted_at.desc())
        .all()
    )

def update_application_status(
    db: Session,
    application_id: UUID,
    new_status: ApplicationStatus,
    remarks: str | None,
    current_user: User,
) -> Application:
    if current_user.role not in {
        UserRole.GOVERNMENT_OFFICIAL,
        UserRole.ADMINISTRATOR,
        UserRole.SUPER_ADMIN,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authorized officials can update application status",
        )

    application = (
        db.query(Application)
        .filter(Application.id == application_id)
        .first()
    )

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    allowed_statuses = ALLOWED_STATUS_TRANSITIONS[application.status]

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot change application status from "
                f"{application.status.value} to {new_status.value}"
            ),
        )

    application.status = new_status

    if remarks is not None:
        application.remarks = remarks

    if new_status == ApplicationStatus.APPROVED:
        application.approved_by = current_user.id
        application.rejection_reason = None

    elif new_status == ApplicationStatus.REJECTED:
        application.approved_by = None
        application.rejection_reason = remarks

    elif new_status != ApplicationStatus.REJECTED:
        application.rejection_reason = None

    send_notification(
        db=db,
        user_id=application.user_id,
        notification_type=NotificationType.APPLICATION_UPDATE,
        title="Application Status Updated",
        message=(
            f"Your application status has been updated to "
            f"{new_status.value.replace('_', ' ').title()}."
        ),
        related_entity_type="application",
        related_entity_id=application.id,
    )

    db.commit()
    db.refresh(application)

    return application