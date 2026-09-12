from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.policies.schemas import (
    PolicyCreate,
    PolicyReject,
    PolicyResponse,
    PolicyUpdate,
)
from backend.app.policies.service import (
    approve_policy,
    archive_policy,
    create_policy,
    get_policy,
    list_policies,
    reject_policy,
    unarchive_policy,
    update_policy,
)

router = APIRouter(
    prefix="/policies",
    tags=["Policies"],
)


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=201,
)
def create_policy_route(
    policy_data: PolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_policy(
        db=db,
        policy_data=policy_data,
        current_user=current_user,
    )


@router.get(
    "",
    response_model=list[PolicyResponse],
)
def list_policies_route(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_policies(
        db=db,
        include_archived=include_archived,
    )


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
)
def get_policy_route(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_policy(
        db=db,
        policy_id=policy_id,
    )


@router.put(
    "/{policy_id}",
    response_model=PolicyResponse,
)
def update_policy_route(
    policy_id: UUID,
    policy_data: PolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_policy(
        db=db,
        policy_id=policy_id,
        policy_data=policy_data,
        current_user=current_user,
    )


@router.post(
    "/{policy_id}/archive",
    response_model=PolicyResponse,
)
def archive_policy_route(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return archive_policy(
        db=db,
        policy_id=policy_id,
        current_user=current_user,
    )


@router.post(
    "/{policy_id}/unarchive",
    response_model=PolicyResponse,
)
def unarchive_policy_route(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return unarchive_policy(
        db=db,
        policy_id=policy_id,
        current_user=current_user,
    )


@router.post(
    "/{policy_id}/approve",
    response_model=PolicyResponse,
)
def approve_policy_route(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return approve_policy(
        db=db,
        policy_id=policy_id,
        current_user=current_user,
    )


@router.post(
    "/{policy_id}/reject",
    response_model=PolicyResponse,
)
def reject_policy_route(
    policy_id: UUID,
    rejection_data: PolicyReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return reject_policy(
        db=db,
        policy_id=policy_id,
        rejection_reason=rejection_data.rejection_reason,
        current_user=current_user,
    )
