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
) -> list[Policy]:
    query = db.query(Policy)

    if current_user.role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        # Admins see all statuses from all users
        if not include_archived:
            query = query.filter(Policy.status != PolicyStatus.ARCHIVED)
    elif current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        # Officials see their own records (all statuses) + APPROVED from others
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
