from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.schemas import (
    RoleRequestSubmit,
    RoleRequestResponse,
    RoleRequestReview,
    MessageResponse,
)
from backend.app.db.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.models.role_request import RoleRequest, RequestedRole, RequestStatus

router = APIRouter(
    prefix="/role-requests",
    tags=["Role Requests"],
)


# Required fields for each role (all other fields are optional)
REQUIRED_DETAILS_FIELDS = {
    "researcher": {"institution_name"},
    "organization": {
        "organization_name",
        "registration_id",
        "authorized_representative",
        "official_email",
    },
    "government_official": {
        "department_ministry",
        "designation",
        "official_id",
        "state",
    },
    "administrator": {
        "official_email",
        "employee_id",
    },
}

# Roles that an administrator can approve
ADMIN_APPROVABLE_ROLES = {"organization", "government_official"}

# Roles that a super admin can approve (super admin ONLY approves admin)
SUPER_ADMIN_APPROVABLE_ROLES = {"administrator"}


def _get_pending_request_count(db: Session, user_id) -> int:
    """Count pending requests for a user."""
    return db.query(RoleRequest).filter(
        and_(
            RoleRequest.user_id == user_id,
            RoleRequest.status == RequestStatus.PENDING,
        )
    ).count()


def _validate_role_details(requested_role: str, details: dict) -> None:
    """Validate that details contain the required fields for the role."""
    required_fields = REQUIRED_DETAILS_FIELDS.get(requested_role, set())
    if not required_fields:
        return

    missing = required_fields - set(details.keys())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields for {requested_role}: {', '.join(sorted(missing))}",
        )


# ─── SUBMIT ROLE REQUEST ────────────────────────────────────────────────────

@router.post(
    "",
    response_model=RoleRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_role_request(
    data: RoleRequestSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Only citizens can request elevated roles
    if current_user.role != UserRole.CITIZEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only citizens can request elevated roles",
        )

    # Validate requested role
    valid_roles = {"researcher", "organization", "government_official", "administrator"}
    if data.requested_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(sorted(valid_roles))}",
        )

    # Check email verification for researcher (requires email verification)
    if data.requested_role == "researcher" and not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification is required to become a researcher",
        )

    # Check for existing pending request
    pending_count = _get_pending_request_count(db, current_user.id)
    if pending_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a pending role request. Cancel it before submitting a new one.",
        )

    # Validate role-specific details
    _validate_role_details(data.requested_role, data.details)

    # Determine initial status
    # Researcher does not require admin approval — auto-approve if email verified
    if data.requested_role == "researcher":
        initial_status = RequestStatus.APPROVED
    else:
        initial_status = RequestStatus.PENDING

    # Create the role request
    role_request = RoleRequest(
        user_id=current_user.id,
        requested_role=data.requested_role,
        status=initial_status,
        details=data.details,
    )

    db.add(role_request)

    # If auto-approved, update the user's role immediately
    if initial_status == RequestStatus.APPROVED:
        current_user.role = UserRole(data.requested_role)
        role_request.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(role_request)

    return role_request


# ─── LIST MY ROLE REQUESTS ──────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[RoleRequestResponse],
)
def list_my_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    requests = (
        db.query(RoleRequest)
        .filter(RoleRequest.user_id == current_user.id)
        .order_by(RoleRequest.created_at.desc())
        .all()
    )
    return requests


# ─── CANCEL PENDING REQUEST ─────────────────────────────────────────────────

@router.put(
    "/{request_id}/cancel",
    response_model=MessageResponse,
)
def cancel_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from uuid import UUID

    try:
        req_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request ID",
        )

    role_request = db.query(RoleRequest).filter(
        and_(
            RoleRequest.id == req_uuid,
            RoleRequest.user_id == current_user.id,
        )
    ).first()

    if not role_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role request not found",
        )

    if role_request.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be cancelled",
        )

    role_request.status = RequestStatus.CANCELLED
    db.commit()

    return {"message": "Request cancelled successfully"}


# ─── GET PENDING REQUESTS (Admin/Super Admin) ──────────────────────────────

@router.get(
    "/pending",
    response_model=list[RoleRequestResponse],
)
def list_pending_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Only administrators and super admins can view pending requests
    if current_user.role not in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view pending requests",
        )

    query = db.query(RoleRequest).filter(
        RoleRequest.status == RequestStatus.PENDING
    )

    if current_user.role == UserRole.SUPER_ADMIN:
        # Super admin only sees administrator requests
        query = query.filter(
            RoleRequest.requested_role == RequestedRole.ADMINISTRATOR
        )
    elif current_user.role == UserRole.ADMINISTRATOR:
        # Admin sees organization and government_official requests
        query = query.filter(
            RoleRequest.requested_role.in_([RequestedRole.ORGANIZATION, RequestedRole.GOVERNMENT_OFFICIAL])
        )

    requests = query.order_by(RoleRequest.created_at.asc()).all()
    return requests


# ─── APPROVE REQUEST ────────────────────────────────────────────────────────

@router.put(
    "/{request_id}/approve",
    response_model=MessageResponse,
)
def approve_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from uuid import UUID

    try:
        req_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request ID",
        )

    role_request = db.query(RoleRequest).filter(
        RoleRequest.id == req_uuid
    ).first()

    if not role_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role request not found",
        )

    if role_request.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be approved",
        )

    requested_role = role_request.requested_role.value

    # Super admin can ONLY approve administrator requests
    if current_user.role == UserRole.SUPER_ADMIN:
        if requested_role not in SUPER_ADMIN_APPROVABLE_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin can only approve Administrator requests",
            )
    # Admin can ONLY approve organization and government_official requests
    elif current_user.role == UserRole.ADMINISTRATOR:
        if requested_role not in ADMIN_APPROVABLE_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator can only approve Organization and Government Official requests",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can approve role requests",
        )

    user = db.get(User, role_request.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = UserRole(requested_role)
    role_request.status = RequestStatus.APPROVED
    role_request.reviewer_id = current_user.id
    role_request.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    return {"message": f"Request approved. User is now a {requested_role}."}


# ─── REJECT REQUEST ─────────────────────────────────────────────────────────

@router.put(
    "/{request_id}/reject",
    response_model=MessageResponse,
)
def reject_request(
    request_id: str,
    review_data: RoleRequestReview,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from uuid import UUID

    try:
        req_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request ID",
        )

    role_request = db.query(RoleRequest).filter(
        RoleRequest.id == req_uuid
    ).first()

    if not role_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role request not found",
        )

    if role_request.status != RequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be rejected",
        )

    requested_role = role_request.requested_role.value

    if current_user.role == UserRole.SUPER_ADMIN:
        if requested_role not in SUPER_ADMIN_APPROVABLE_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin can only reject Administrator requests",
            )
    elif current_user.role == UserRole.ADMINISTRATOR:
        if requested_role not in ADMIN_APPROVABLE_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator can only reject Organization and Government Official requests",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can reject role requests",
        )

    role_request.status = RequestStatus.REJECTED
    role_request.reviewer_id = current_user.id
    role_request.reviewed_at = datetime.now(timezone.utc)
    role_request.review_reason = review_data.review_reason

    db.commit()
    return {"message": "Request rejected"}
