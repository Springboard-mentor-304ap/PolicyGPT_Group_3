from datetime import date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.policy import Policy, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.user import User, UserRole
from backend.app.models.notification import NotificationType
from backend.app.notifications.service import send_notification
from backend.app.policies.schemas import (
    PolicyCreate,
    PolicyDetailResponse,
    PolicyResponse,
    PolicySchemeSummary,
    PolicyUpdate,
)
# Reuses the existing department-scope rule (profile department, 403 when the
# profile is missing) the analytics, reports and applications modules already
# apply to government officials.
from backend.app.analytics.service import _get_official_ministry


# Government officials may only work on policies of their own ministry: a
# policy is attributed through `Policy.ministry` — the same field analytics
# and reports scope official data by. Records without a ministry fall back to
# their department, which holds the same kind of value in the existing data.


def _policy_owner(policy: Policy) -> str | None:
    return policy.ministry or policy.department


def _policy_is_in_scope(policy: Policy, scope: str) -> bool:
    owner = _policy_owner(policy)

    return bool(owner) and owner.strip().casefold() == scope.strip().casefold()


def _enforce_scope(
    ministry: str | None,
    department: str | None,
    scope: str,
) -> None:
    """Reject a policy outside the official's own ministry/department.

    A policy is owned by its ministry, so the submitted ministry has to match
    the official's scope. Records that carry no ministry at all are attributed
    through their department instead (both fields hold the same kind of value
    in the existing data). Used for both creation and edits that move the
    policy, so the API cannot be used to escape the scope.
    """
    owner = (ministry or "").strip() or (department or "").strip()

    if owner and owner.casefold() == scope.strip().casefold():
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "You can only manage policies for your own ministry/department "
            f'("{scope}")'
        ),
    )


def create_policy(
    db: Session,
    policy_data: PolicyCreate,
    current_user: User,
) -> Policy:
    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can create policies",
        )

    scope = _get_official_ministry(db, current_user)
    _enforce_scope(policy_data.ministry, policy_data.department, scope)

    policy = Policy(
        title=policy_data.title,
        description=policy_data.description,
        required_documents=policy_data.required_documents,
        category=policy_data.category,
        department=policy_data.department,
        ministry=policy_data.ministry,
        state=policy_data.state,
        document_url=policy_data.document_url,
        published_date=policy_data.published_date,
        status=PolicyStatus.PENDING_APPROVAL,
        uploaded_by=current_user.id,
    )

    db.add(policy)
    db.commit()
    db.refresh(policy)

    return policy


def get_policy(
    db: Session,
    policy_id: UUID,
) -> Policy:
    policy = db.get(Policy, policy_id)

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    return policy


def get_policy_details(
    db: Session,
    policy_id: UUID,
    current_user: User,
) -> PolicyDetailResponse:
    policy = get_policy(db, policy_id)

    # Officials can only open policies of their own ministry; administrators
    # and the public discovery roles stay unrestricted.
    if current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        scope = _get_official_ministry(db, current_user)

        if not _policy_is_in_scope(policy, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This policy is outside your department scope",
            )

    query = db.query(Scheme).filter(Scheme.policy_id == policy.id)

    if current_user.role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        query = query.filter(Scheme.status != SchemeStatus.ARCHIVED)
    elif current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        query = query.filter(
            (Scheme.created_by == current_user.id)
            | (Scheme.status == SchemeStatus.ACTIVE)
        ).filter(Scheme.status != SchemeStatus.ARCHIVED)
    else:
        query = query.filter(Scheme.status == SchemeStatus.ACTIVE)

    schemes = query.order_by(Scheme.created_at.desc()).all()
    policy_data = PolicyResponse.model_validate(policy).model_dump()
    return PolicyDetailResponse(
        **policy_data,
        schemes=[PolicySchemeSummary.model_validate(scheme) for scheme in schemes],
    )


def list_policies(
    db: Session,
    current_user: User,
    include_archived: bool = False,
    by_me: bool = False,
) -> list[Policy]:
    query = db.query(Policy)

    if current_user.role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        # Admins see all statuses from all users; `by_me` is only offered to
        # officials, so their behaviour is unchanged.
        if not include_archived:
            query = query.filter(Policy.status != PolicyStatus.ARCHIVED)
    elif current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        # Officials are locked to their own ministry. Inside that scope they
        # see their own records (all statuses) + APPROVED records from other
        # officials, or only their own records when "By Me" is selected.
        scope = _get_official_ministry(db, current_user)
        query = query.filter(
            Policy.ministry == scope
        )
        if by_me:
            query = query.filter(Policy.uploaded_by == current_user.id)
        else:
            query = query.filter(
                (Policy.uploaded_by == current_user.id)
                | (Policy.status == PolicyStatus.APPROVED)
            )
        if not include_archived:
            query = query.filter(Policy.status != PolicyStatus.ARCHIVED)
    else:
        # Citizens, researchers, organizations: APPROVED only
        query = query.filter(Policy.status == PolicyStatus.APPROVED)

    return query.order_by(
        Policy.created_at.desc()
    ).all()


def update_policy(
    db: Session,
    policy_id: UUID,
    policy_data: PolicyUpdate,
    current_user: User,
) -> Policy:
    policy = get_policy(db, policy_id)

    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can update policies",
        )

    if policy.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update policies you uploaded",
        )

    if policy.status == PolicyStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved policies cannot be updated. Archive the policy first.",
        )

    update_fields = policy_data.model_dump(exclude_unset=True)

    if "ministry" in update_fields or "department" in update_fields:
        # An edit may not move the policy out of the official's own scope.
        # Editing other fields of a pre-existing record is untouched.
        candidate_ministry = update_fields.get("ministry", policy.ministry)
        candidate_department = update_fields.get("department", policy.department)
        scope_changed = (
            (candidate_ministry or "").strip()
            != (policy.ministry or "").strip()
            or (candidate_department or "").strip()
            != (policy.department or "").strip()
        )

        if scope_changed:
            scope = _get_official_ministry(db, current_user)
            _enforce_scope(candidate_ministry, candidate_department, scope)

    if policy.status == PolicyStatus.ARCHIVED:
        update_data = policy_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(policy, field, value)

        db.commit()
        db.refresh(policy)

        return policy

    if policy.status == PolicyStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Policy is pending approval and cannot be updated",
        )

    if policy.status == PolicyStatus.REJECTED:
        update_data = policy_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(policy, field, value)

        policy.status = PolicyStatus.PENDING_APPROVAL
        policy.rejection_reason = None
        policy.approved_by = None

        db.commit()
        db.refresh(policy)

        return policy

    if policy.status == PolicyStatus.DRAFT:
        update_data = policy_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(policy, field, value)

        db.commit()
        db.refresh(policy)

        return policy

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Policy cannot be updated in its current state",
    )


def archive_policy(
    db: Session,
    policy_id: UUID,
    current_user: User,
) -> Policy:
    policy = get_policy(db, policy_id)

    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can archive policies",
        )

    if policy.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only archive policies you uploaded",
        )

    scope = _get_official_ministry(db, current_user)

    if not _policy_is_in_scope(policy, scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This policy is outside your department scope",
        )

    if policy.status == PolicyStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Policy is already archived",
        )

    policy.status = PolicyStatus.ARCHIVED
    policy.archived_at = datetime.utcnow()

    db.commit()
    db.refresh(policy)

    return policy


def unarchive_policy(
    db: Session,
    policy_id: UUID,
    current_user: User,
) -> Policy:
    policy = get_policy(db, policy_id)

    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can unarchive policies",
        )

    if policy.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only unarchive policies you uploaded",
        )

    if policy.status != PolicyStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only archived policies can be unarchived",
        )

    policy.status = PolicyStatus.PENDING_APPROVAL
    policy.archived_at = None
    policy.approved_by = None
    policy.rejection_reason = None

    db.commit()
    db.refresh(policy)

    return policy


def approve_policy(
    db: Session,
    policy_id: UUID,
    current_user: User,
) -> Policy:
    policy = get_policy(db, policy_id)

    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can approve policies",
        )

    if policy.status != PolicyStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending policies can be approved",
        )

    policy.status = PolicyStatus.APPROVED
    policy.approved_by = current_user.id
    policy.rejection_reason = None

    if policy.published_date is None:
        policy.published_date = date.today()
    send_notification(
        db=db,
        user_id=policy.uploaded_by,
        notification_type=NotificationType.NEW_POLICY,
        title="Policy Approved",
        message=f'Your policy "{policy.title}" has been approved and published',
        related_entity_type="policy",
        related_entity_id=policy.id,
    )
    recipients = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            User.role.in_(
                [
                    UserRole.CITIZEN,
                    UserRole.RESEARCHER,
                    UserRole.ORGANIZATION,
                ]
            ),
            User.id != policy.uploaded_by,
        )
        .all()
    )

    for recipient in recipients:
        send_notification(
            db=db,
            user_id=recipient.id,
            notification_type=NotificationType.NEW_POLICY,
            title="New Policy Published",
            message=f'A new policy "{policy.title}" has been published.',
            related_entity_type="policy",
            related_entity_id=policy.id,
        )
    db.commit()
    db.refresh(policy)

    return policy


def reject_policy(
    db: Session,
    policy_id: UUID,
    rejection_reason: str,
    current_user: User,
) -> Policy:
    policy = get_policy(db, policy_id)

    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can reject policies",
        )

    if policy.status != PolicyStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending policies can be rejected",
        )

    if not rejection_reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is required",
        )

    policy.status = PolicyStatus.REJECTED
    policy.rejection_reason = rejection_reason
    policy.approved_by = None

    db.commit()
    db.refresh(policy)

    return policy
