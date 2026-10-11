import logging
from datetime import date, datetime, timezone
from typing import Callable
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.audit.service import client_ip, log_action
from backend.app.models.policy import Policy, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.user import User, UserRole
from backend.app.models.notification import NotificationType
from backend.app.notifications.service import (
    queue_notifications,
    send_notification,
)
from backend.app.pagination import DEFAULT_LIMIT, clamp_limit
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
from backend.app.ai.sync_service import schedule_policy_sync
from backend.app.analytics.service import _get_official_ministry
# One canonical scope rule (case-insensitive, trimmed, ministry first with
# department fallback) shared with schemes, applications, search, analytics
# and reports — see backend/app/scope.py.
from backend.app.scope import is_in_scope, policy_in_scope, policy_scope_filter

logger = logging.getLogger(__name__)

# Audit log actions recorded for the policies module.
AUDIT_POLICY_APPROVE = "policy.approve"
AUDIT_POLICY_REJECT = "policy.reject"
AUDIT_POLICY_ARCHIVE = "policy.archive"
AUDIT_POLICY_UNARCHIVE = "policy.unarchive"


def _audit_policy_action(
    db: Session,
    current_user: User,
    action: str,
    policy: Policy,
    old_status: str,
    new_status: str,
    request: Request | None,
) -> None:
    """Stage one audit row in the caller's open transaction.

    The row is deliberately not committed here: the change and its audit
    entry are published together or not at all.
    """

    log_action(
        db=db,
        actor_id=current_user.id,
        action=action,
        target_table="policies",
        target_id=policy.id,
        changes={"status": {"old": old_status, "new": new_status}},
        ip_address=client_ip(request),
    )


def _notify_policy_rejected(
    db: Session,
    current_user: User,
    policy: Policy,
) -> None:
    """Tell the uploader a policy was rejected, with the stated reason.

    Only the reject path calls this — approval and archiving tell the
    uploader something else — and it never notifies the acting admin.
    """

    if not policy.uploaded_by or policy.uploaded_by == current_user.id:
        return

    queue_notifications(
        db=db,
        user_ids=[policy.uploaded_by],
        notification_type=NotificationType.POLICY_REJECTED,
        title="Policy Rejected",
        message=(
            f'Your policy "{policy.title}" was rejected.\n'
            f"Reason: {policy.rejection_reason}"
        ),
        related_entity_type="policy",
        related_entity_id=policy.id,
    )


# Government officials may only work on policies of their own ministry: a
# policy is attributed through `Policy.ministry` — the same field analytics
# and reports scope official data by. Records without a ministry fall back to
# their department, which holds the same kind of value in the existing data.

# Columns of `policies` that are NOT NULL in the database. An explicit JSON
# null for one of them would otherwise be written through and fail with an
# IntegrityError (500) at commit; the API rejects it up front instead — the
# same rule the FAQ module applies to its update endpoint.
NON_NULLABLE_UPDATE_FIELDS = (
    "title",
    "description",
    "category",
    "department",
)


def _policy_is_in_scope(policy: Policy, scope: str) -> bool:
    return policy_in_scope(policy, scope)


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
    if is_in_scope(ministry, department, scope):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "You can only manage policies for your own ministry/department "
            f'("{scope}")'
        ),
    )


def _notify_admins_awaiting_approval(
    db: Session,
    actor: User,
    title: str,
    message: str,
    related_entity_type: str,
    related_entity_id: UUID,
) -> None:
    """Queue APPROVAL_PENDING to every administrator in one query.

    Recipients are resolved with a single query and staged in the caller's
    open transaction, so the alert costs no query per administrator and is
    published together with the record. The acting official is excluded.
    """

    recipients = (
        db.query(User.id)
        .filter(
            User.is_active.is_(True),
            User.role == UserRole.ADMINISTRATOR,
            User.id != actor.id,
        )
        .all()
    )

    if not recipients:
        return

    queue_notifications(
        db=db,
        user_ids=[row[0] for row in recipients],
        notification_type=NotificationType.APPROVAL_PENDING,
        title=title,
        message=message,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
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
    # Flush inside the same transaction so the server-generated id exists for
    # the notification below; nothing is committed until db.commit().
    db.flush()

    # Queued in the same transaction as the insert: administrators learn
    # about the pending policy together with the row itself, and no alert
    # survives a failed commit.
    _notify_admins_awaiting_approval(
        db,
        current_user,
        title="Policy Awaiting Approval",
        message=(
            f'The policy "{policy.title}" has been submitted and is '
            "waiting for approval."
        ),
        related_entity_type="policy",
        related_entity_id=policy.id,
    )

    db.commit()
    db.refresh(policy)

    try:
        schedule_policy_sync(policy.id, expected_updated_at=policy.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for policy %s: %s",
            policy.id,
            exc,
        )

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


def _assert_policy_is_visible(
    db: Session,
    policy: Policy,
    current_user: User,
) -> None:
    """Reject reads of policies the caller may not see.

    Mirrors the discovery rules of `list_policies`:

    * administrators see every status;
    * the uploader (owner) always sees their own record;
    * everyone else only sees APPROVED policies.

    Officials are additionally locked to their own ministry/department. A
    record the caller may not see answers 404 (not 403) so its existence is
    not revealed; an out-of-scope official keeps the existing 403.
    """
    if current_user.role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        return

    if current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        scope = _get_official_ministry(db, current_user)

        if not _policy_is_in_scope(policy, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This policy is outside your department scope",
            )

    if (
        policy.uploaded_by == current_user.id
        or policy.status == PolicyStatus.APPROVED
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Policy not found",
    )


def _count_policy_view(
    db: Session,
    policy: Policy,
    current_user: User,
) -> None:
    """Bump `view_count` for a visit that is actually counted.

    The increment happens in SQL (``view_count = view_count + 1``) so
    concurrent readers cannot lose an update. Views by the policy's owner and
    by administrators are ignored, and callers only reach this after the
    visibility check, so requests that end in 403/404 never count.
    """
    if current_user.role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        return

    if policy.uploaded_by == current_user.id:
        return

    (
        db.query(Policy)
        .filter(Policy.id == policy.id)
        .update(
            {Policy.view_count: Policy.view_count + 1},
            synchronize_session=False,
        )
    )
    db.commit()
    db.refresh(policy)


def get_policy_details(
    db: Session,
    policy_id: UUID,
    current_user: User,
) -> PolicyDetailResponse:
    policy = get_policy(db, policy_id)
    _assert_policy_is_visible(db, policy, current_user)
    _count_policy_view(db, policy, current_user)

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
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[Policy], int]:
    """Policies the caller may see, newest first, paged.

    Returns ``(rows, total)`` — `total` counts every matching row before
    LIMIT/OFFSET, which is what the X-Total-Count header carries.
    """
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
            policy_scope_filter(scope)
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

    total = query.count()

    rows = (
        query.order_by(Policy.created_at.desc())
        .offset(offset)
        .limit(clamp_limit(limit))
        .all()
    )

    return rows, total


def update_policy(
    db: Session,
    policy_id: UUID,
    policy_data: PolicyUpdate,
    current_user: User,
) -> Policy:
    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can update policies",
        )

    policy = get_policy(db, policy_id)

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

    for field in NON_NULLABLE_UPDATE_FIELDS:
        if field in update_fields and update_fields[field] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} cannot be null",
            )

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

        try:
            schedule_policy_sync(policy.id, expected_updated_at=policy.updated_at)
        except Exception as exc:
            # The authoritative transaction already committed; scheduling must
            # not fail the request, but the miss is never silent.
            logger.warning(
                "Knowledge sync scheduling failed for policy %s: %s",
                policy.id,
                exc,
            )

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

        try:
            schedule_policy_sync(policy.id, expected_updated_at=policy.updated_at)
        except Exception as exc:
            # The authoritative transaction already committed; scheduling must
            # not fail the request, but the miss is never silent.
            logger.warning(
                "Knowledge sync scheduling failed for policy %s: %s",
                policy.id,
                exc,
            )

        return policy

    if policy.status == PolicyStatus.DRAFT:
        update_data = policy_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(policy, field, value)

        db.commit()
        db.refresh(policy)

        try:
            schedule_policy_sync(policy.id, expected_updated_at=policy.updated_at)
        except Exception as exc:
            # The authoritative transaction already committed; scheduling must
            # not fail the request, but the miss is never silent.
            logger.warning(
                "Knowledge sync scheduling failed for policy %s: %s",
                policy.id,
                exc,
            )

        return policy

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Policy cannot be updated in its current state",
    )


def archive_policy(
    db: Session,
    policy_id: UUID,
    current_user: User,
    request: Request | None = None,
) -> Policy:
    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can archive policies",
        )

    policy = get_policy(db, policy_id)

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

    old_status = policy.status

    policy.status = PolicyStatus.ARCHIVED
    policy.archived_at = datetime.now(timezone.utc)

    _audit_policy_action(
        db,
        current_user,
        AUDIT_POLICY_ARCHIVE,
        policy,
        old_status.value,
        PolicyStatus.ARCHIVED.value,
        request,
    )

    db.commit()
    db.refresh(policy)

    try:
        schedule_policy_sync(policy.id, expected_updated_at=policy.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for policy %s: %s",
            policy.id,
            exc,
        )

    return policy


def unarchive_policy(
    db: Session,
    policy_id: UUID,
    current_user: User,
    request: Request | None = None,
) -> Policy:
    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can unarchive policies",
        )

    policy = get_policy(db, policy_id)

    if policy.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only unarchive policies you uploaded",
        )

    # Same department-scope rule as archiving: an official may not bring a
    # policy back from archive when it sits outside their ministry.
    scope = _get_official_ministry(db, current_user)

    if not _policy_is_in_scope(policy, scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This policy is outside your department scope",
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

    _audit_policy_action(
        db,
        current_user,
        AUDIT_POLICY_UNARCHIVE,
        policy,
        PolicyStatus.ARCHIVED.value,
        PolicyStatus.PENDING_APPROVAL.value,
        request,
    )

    db.commit()
    db.refresh(policy)

    try:
        schedule_policy_sync(policy.id, expected_updated_at=policy.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for policy %s: %s",
            policy.id,
            exc,
        )

    return policy


def approve_policy(
    db: Session,
    policy_id: UUID,
    current_user: User,
    request: Request | None = None,
) -> Policy:
    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can approve policies",
        )

    policy = get_policy(db, policy_id)

    if policy.status != PolicyStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending policies can be approved",
        )

    old_status = policy.status

    policy.status = PolicyStatus.APPROVED
    policy.approved_by = current_user.id
    policy.rejection_reason = None

    _audit_policy_action(
        db,
        current_user,
        AUDIT_POLICY_APPROVE,
        policy,
        old_status.value,
        PolicyStatus.APPROVED.value,
        request,
    )

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

    try:
        schedule_policy_sync(policy.id, expected_updated_at=policy.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for policy %s: %s",
            policy.id,
            exc,
        )

    return policy


def reject_policy(
    db: Session,
    policy_id: UUID,
    rejection_reason: str,
    current_user: User,
    request: Request | None = None,
) -> Policy:
    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can reject policies",
        )

    policy = get_policy(db, policy_id)

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

    old_status = policy.status

    policy.status = PolicyStatus.REJECTED
    policy.rejection_reason = rejection_reason
    policy.approved_by = None

    _audit_policy_action(
        db,
        current_user,
        AUDIT_POLICY_REJECT,
        policy,
        old_status.value,
        PolicyStatus.REJECTED.value,
        request,
    )

    # Queued before the commit: the alert lands only if the rejection does.
    _notify_policy_rejected(db, current_user, policy)

    db.commit()
    db.refresh(policy)

    try:
        schedule_policy_sync(policy.id, expected_updated_at=policy.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for policy %s: %s",
            policy.id,
            exc,
        )

    return policy
