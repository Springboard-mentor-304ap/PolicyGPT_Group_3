from datetime import date
from uuid import UUID
from fastapi import HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.audit.service import client_ip, log_action
from backend.app.models.application import Application, ApplicationStatus
from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)
from backend.app.models.policy import Policy
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.user import User, UserRole
from backend.app.models.notification import NotificationType
from backend.app.notifications.service import queue_notifications, send_notification
from backend.app.applications.schemas import (
    ApplicationReviewResponse,
    MyApplicationResponse,
)
from backend.app.pagination import DEFAULT_LIMIT, clamp_limit
# Reuses the exact department-scope logic the analytics module applies to
# government officials (profile department, 403 when the profile is missing).
from backend.app.analytics.service import _get_official_ministry
# One canonical scope rule shared with policies, schemes, search, analytics
# and reports — see backend/app/scope.py.
from backend.app.scope import (
    normalized_match,
    normalize,
    scheme_in_scope,
    scheme_scope_filter,
)

# Audit log actions recorded for the applications module.
AUDIT_APPLICATION_STATUS_CHANGE = "application.status_change"
AUDIT_APPLICATION_WITHDRAW = "application.withdraw"

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
    # WITHDRAWN is terminal and only reachable through the applicant-facing
    # `withdraw_application` below — staff status updates cannot set it.
    ApplicationStatus.WITHDRAWN: set(),
}

# Statuses the applicant may still pull back themselves. Decided
# applications (APPROVED / REJECTED) and staff-driven review states are not
# withdrawable: WITHDRAWN is reached only from these two.
WITHDRAWABLE_STATUSES = {
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.ADDITIONAL_INFORMATION_REQUIRED,
}

# Staff roles allowed to view/update application status (mirrors the
# authorization check previously inlined in update_application_status).
# Application approvals belong to government officials only: administrators
# and super administrators are deliberately excluded so they never see,
# receive or process citizen application work.
APPLICATION_REVIEW_ROLES = {
    UserRole.GOVERNMENT_OFFICIAL,
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

    # A scheme may still be ACTIVE after its application window closed — the
    # deadline is the authoritative cutoff for submissions.
    if (
        scheme.deadline_date is not None
        and scheme.deadline_date < date.today()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The application deadline for this scheme has passed",
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
    # Flush inside the same transaction so the server-generated id exists for
    # the notification below; nothing is committed yet.
    db.flush()

    # NEW_APPLICATION to the officials that can actually review it: those
    # whose department matches the scheme's department or its parent policy's
    # ministry (the canonical scope rule in backend/app/scope.py). The query
    # returns nothing when no official is in scope, so this is a no-op then.
    scope_clauses = []

    # Resolve the scheme's department and its parent policy's ministry in one
    # query — the same lookup `_application_matches_department` uses.
    scheme_scope_row = (
        db.query(Scheme.department, Policy.ministry)
        .select_from(Scheme)
        .join(Policy, Policy.id == Scheme.policy_id)
        .filter(Scheme.id == scheme.id)
        .first()
    )
    scheme_department, policy_ministry = scheme_scope_row or (None, None)

    for scope_value in (scheme_department, policy_ministry):
        if normalize(scope_value) is not None:
            scope_clauses.append(
                normalized_match(GovernmentOfficialProfile.department, scope_value)
            )

    if scope_clauses:
        recipients = (
            db.query(User.id)
            .join(
                GovernmentOfficialProfile,
                GovernmentOfficialProfile.user_id == User.id,
            )
            .filter(
                User.is_active.is_(True),
                User.role == UserRole.GOVERNMENT_OFFICIAL,
                User.id != current_user.id,
                or_(*scope_clauses),
            )
            .all()
        )

        if recipients:
            queue_notifications(
                db=db,
                user_ids=[row[0] for row in recipients],
                notification_type=NotificationType.NEW_APPLICATION,
                title="New Application Received",
                message=(
                    f'A new application for "{scheme.title}" has been '
                    "submitted and is waiting for review."
                ),
                related_entity_type="application",
                related_entity_id=application.id,
            )

    # The check above is friendly, but two concurrent submissions can both
    # pass it. The unique constraint on (user_id, scheme_id) is the real
    # guard; losing that race is reported exactly like the duplicate check.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already applied for this scheme",
        )

    db.refresh(application)

    return application


def _application_matches_department(
    db: Session,
    application: Application,
    department: str,
) -> bool:
    """True when the application's scheme sits in the given department/ministry.

    Scope matches either the scheme's own department or its parent policy's
    ministry — the canonical rule from backend/app/scope.py, now
    case-insensitive and trimmed so it agrees with the review list.
    """
    row = (
        db.query(Scheme.department, Policy.ministry)
        .select_from(Scheme)
        .join(Policy, Policy.id == Scheme.policy_id)
        .filter(Scheme.id == application.scheme_id)
        .first()
    )
    if not row:
        return False
    scheme_department, policy_ministry = row
    return scheme_in_scope(scheme_department, policy_ministry, department)


def list_applications_for_review(
    db: Session,
    status_filter: ApplicationStatus | None,
    current_user: User,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[ApplicationReviewResponse], int]:
    """Returns ``(rows, total)``; `total` is the pre-paging count for the
    X-Total-Count header."""
    """Applications the current staff member is authorized to review.

    - Government officials only see applications in their own
      department/ministry (server-side scope, same rules as analytics).
    - Administrators / super admins are not part of this workflow: the
      role check below rejects them (application approvals are official-only
      work).
    - Applicants and scheme context are joined in so the UI does not need
      extra round-trips.
    """
    if current_user.role not in APPLICATION_REVIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authorized officials can review applications",
        )

    department = _get_official_ministry(db, current_user)

    query = (
        db.query(
            Application,
            User.full_name,
            Scheme.title,
            Scheme.department,
            Policy.ministry,
        )
        .join(User, User.id == Application.user_id)
        .join(Scheme, Scheme.id == Application.scheme_id)
        .join(Policy, Policy.id == Scheme.policy_id)
    )

    if department:
        query = query.filter(
            scheme_scope_filter(department)
        )

    if status_filter is not None:
        query = query.filter(Application.status == status_filter)

    total = query.count()

    rows = (
        query.order_by(Application.submitted_at.desc())
        .offset(offset)
        .limit(clamp_limit(limit))
        .all()
    )

    return [
        ApplicationReviewResponse(
            id=application.id,
            user_id=application.user_id,
            scheme_id=application.scheme_id,
            status=application.status,
            remarks=application.remarks,
            approved_by=application.approved_by,
            rejection_reason=application.rejection_reason,
            submitted_at=application.submitted_at,
            updated_at=application.updated_at,
            applicant_name=applicant_name or None,
            scheme_title=scheme_title,
            scheme_department=scheme_department,
            policy_ministry=policy_ministry,
        )
        for (
            application,
            applicant_name,
            scheme_title,
            scheme_department,
            policy_ministry,
        ) in rows
    ], total

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

    # Only the applicant and government officials may open an application:
    # administrators are deliberately outside the approval workflow.
    if (
        application.user_id != current_user.id
        and current_user.role != UserRole.GOVERNMENT_OFFICIAL
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view this application",
        )

    # Officials may only open applications in their own department/ministry,
    # exactly like the review list and the status-update endpoint. Without
    # this, any official could open any application by UUID.
    if current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        department = _get_official_ministry(db, current_user)

        if not _application_matches_department(db, application, department):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This application is outside your department scope",
            )

    return application

def list_my_applications(
    db: Session,
    current_user: User,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[MyApplicationResponse], int]:
    """The applicant's own applications with scheme context, paged.

    The scheme columns are joined in so the list needs no extra round-trip
    per row; a LEFT join keeps an application visible even if its scheme row
    were ever missing (the extra fields are then null).
    """
    query = (
        db.query(
            Application,
            Scheme.title,
            Scheme.department,
            Scheme.deadline_date,
        )
        .outerjoin(Scheme, Scheme.id == Application.scheme_id)
        .filter(Application.user_id == current_user.id)
    )

    total = query.count()

    rows = (
        query.order_by(Application.submitted_at.desc())
        .offset(offset)
        .limit(clamp_limit(limit))
        .all()
    )

    return [
        MyApplicationResponse(
            id=application.id,
            user_id=application.user_id,
            scheme_id=application.scheme_id,
            status=application.status,
            remarks=application.remarks,
            approved_by=application.approved_by,
            rejection_reason=application.rejection_reason,
            submitted_at=application.submitted_at,
            updated_at=application.updated_at,
            scheme_title=scheme_title,
            scheme_department=scheme_department,
            scheme_deadline_date=scheme_deadline_date,
        )
        for (
            application,
            scheme_title,
            scheme_department,
            scheme_deadline_date,
        ) in rows
    ], total

def update_application_status(
    db: Session,
    application_id: UUID,
    new_status: ApplicationStatus,
    remarks: str | None,
    current_user: User,
    request: Request | None = None,
) -> Application:
    if current_user.role not in APPLICATION_REVIEW_ROLES:
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

    old_status = application.status

    # Department scope: a government official may only touch applications
    # belonging to their own department/ministry (admins are unrestricted).
    if current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        department = _get_official_ministry(db, current_user)
        if not _application_matches_department(db, application, department):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This application is outside your department scope",
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

    # A rejection without remarks stores a null reason, which leaves the
    # applicant with no explanation and no way to fix the application.
    if (
        new_status == ApplicationStatus.REJECTED
        and (remarks is None or not remarks.strip())
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remarks are required when rejecting an application",
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

    # Staged in the caller's open transaction: the status change, its
    # notification and its audit entry publish together or not at all.
    log_action(
        db=db,
        actor_id=current_user.id,
        action=AUDIT_APPLICATION_STATUS_CHANGE,
        target_table="applications",
        target_id=application.id,
        changes={
            "status": {"old": old_status.value, "new": new_status.value}
        },
        ip_address=client_ip(request),
    )

    db.commit()
    db.refresh(application)

    return application


def withdraw_application(
    db: Session,
    application_id: UUID,
    current_user: User,
    request: Request | None = None,
) -> Application:
    """Withdraw the caller's own in-progress application.

    Only statuses the workflow can still leave (SUBMITTED and
    ADDITIONAL_INFORMATION_REQUIRED) may be withdrawn; APPROVED and REJECTED
    stay final, and the unique (user, scheme) constraint still prevents a
    fresh application afterwards. Per product decision, no notification is
    sent for a withdrawal.
    """
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

    if application.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only withdraw your own applications",
        )

    if application.status not in WITHDRAWABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot change application status from "
                f"{application.status.value} to "
                f"{ApplicationStatus.WITHDRAWN.value}"
            ),
        )

    old_status = application.status

    application.status = ApplicationStatus.WITHDRAWN

    # Per product decision above, no notification is sent for a withdrawal —
    # the applicant is the actor. The status change is still audited.
    log_action(
        db=db,
        actor_id=current_user.id,
        action=AUDIT_APPLICATION_WITHDRAW,
        target_table="applications",
        target_id=application.id,
        changes={
            "status": {"old": old_status.value, "new": ApplicationStatus.WITHDRAWN.value}
        },
        ip_address=client_ip(request),
    )

    db.commit()
    db.refresh(application)

    return application