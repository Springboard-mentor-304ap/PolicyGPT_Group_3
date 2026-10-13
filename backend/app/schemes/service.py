import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.audit.service import client_ip, log_action
from backend.app.pagination import DEFAULT_LIMIT, clamp_limit
from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
    EligibilityRule,
)
from backend.app.models.notification import NotificationType
from backend.app.models.policy import Policy, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.user import User, UserRole
from backend.app.models.user_profile import Gender, SocialCategory
from backend.app.notifications.service import queue_notifications, send_notification
from backend.app.schemes.schemas import SchemeCreate, SchemeUpdate
from backend.app.ai.sync_service import schedule_scheme_sync
from backend.app.analytics.service import _get_official_ministry
from backend.app.scope import scheme_in_scope, scheme_scope_filter

logger = logging.getLogger(__name__)

AUDIT_SCHEME_APPROVE = "scheme.approve"
AUDIT_SCHEME_REJECT = "scheme.reject"
AUDIT_SCHEME_ARCHIVE = "scheme.archive"
AUDIT_SCHEME_UNARCHIVE = "scheme.unarchive"

SCHEME_UPDATE_RECIPIENT_ROLES = (
    UserRole.CITIZEN,
    UserRole.RESEARCHER,
    UserRole.ORGANIZATION,
)
PUBLIC_SCHEME_ROLES = frozenset({
    UserRole.CITIZEN,
    UserRole.RESEARCHER,
    UserRole.ORGANIZATION,
})

NON_NULLABLE_UPDATE_FIELDS = ("title", "description", "category")

GENDER_RULE_VALUES = {gender.value for gender in Gender}
SOCIAL_CATEGORY_RULE_VALUES = {
    category.value for category in SocialCategory
}


CATEGORICAL_RULE_OPERATORS = frozenset(
    {
        EligibilityOperator.EQ,
        EligibilityOperator.NEQ,
        EligibilityOperator.IN,
        EligibilityOperator.NOT_IN,
    }
)

NUMERIC_RULE_OPERATORS = frozenset(
    {
        EligibilityOperator.EQ,
        EligibilityOperator.NEQ,
        EligibilityOperator.LT,
        EligibilityOperator.LTE,
        EligibilityOperator.GT,
        EligibilityOperator.GTE,
        EligibilityOperator.IN,
    }
)

PARAMETER_OPERATOR_COMPATIBILITY: dict[
    EligibilityParameter, frozenset[EligibilityOperator]
] = {
    EligibilityParameter.AGE: NUMERIC_RULE_OPERATORS,
    EligibilityParameter.INCOME: NUMERIC_RULE_OPERATORS,
    EligibilityParameter.GENDER: CATEGORICAL_RULE_OPERATORS,
    EligibilityParameter.OCCUPATION: CATEGORICAL_RULE_OPERATORS,
    EligibilityParameter.EDUCATION: CATEGORICAL_RULE_OPERATORS,
    EligibilityParameter.STATE: CATEGORICAL_RULE_OPERATORS,
    EligibilityParameter.DISTRICT: CATEGORICAL_RULE_OPERATORS,
    EligibilityParameter.SOCIAL_CATEGORY: CATEGORICAL_RULE_OPERATORS,
    EligibilityParameter.DISABILITY_STATUS: frozenset(
        {EligibilityOperator.EQ, EligibilityOperator.NEQ}
    ),
}


def _validate_rule_operator(
    parameter: EligibilityParameter,
    operator: EligibilityOperator,
) -> None:
    """Reject an operator that does not suit its parameter with a 400."""
    allowed = PARAMETER_OPERATOR_COMPATIBILITY.get(parameter)

    if allowed is None or operator not in allowed:
        allowed_text = (
            ", ".join(sorted(op.value for op in allowed))
            if allowed
            else "none"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Operator '{operator.value}' is not valid for parameter "
                f"'{parameter.value}'; allowed operators: {allowed_text}"
            ),
        )


def _validate_rule_value(
    parameter: EligibilityParameter,
    value: str,
    operator: EligibilityOperator,
) -> str:
    """Validate a rule value against its parameter and operator.

    Raises 400 with a client-safe message instead of storing a value that
    would raise when the eligibility rules are evaluated later.

    For IN/NOT_IN the value is a comma-separated list: no entry may be empty
    and every entry must be a valid value for the parameter.
    """
    cleaned = value.strip()

    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rule value is required for {parameter.value}",
        )

    if operator in (EligibilityOperator.IN, EligibilityOperator.NOT_IN):
        parts = [part.strip() for part in cleaned.split(",")]

        if any(not part for part in parts):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{parameter.value} rule value must be a "
                    "comma-separated list without empty entries"
                ),
            )

        for part in parts:
            _validate_single_rule_value(parameter, part)

        return cleaned

    _validate_single_rule_value(parameter, cleaned)

    return cleaned


def _validate_single_rule_value(
    parameter: EligibilityParameter,
    cleaned: str,
) -> None:
    if parameter == EligibilityParameter.AGE:
        try:
            age = int(cleaned)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Age rule value must be a whole number of years",
            )

        if age < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Age rule value cannot be negative",
            )

    elif parameter == EligibilityParameter.INCOME:
        try:
            amount = Decimal(cleaned)
        except InvalidOperation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Income rule value must be a number",
            )

        if not amount.is_finite() or amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Income rule value must be a non-negative amount",
            )

    elif parameter == EligibilityParameter.DISABILITY_STATUS:
        if cleaned.lower() not in {"true", "false"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Disability rule value must be "true" or "false"',
            )

    elif parameter == EligibilityParameter.GENDER:
        if cleaned.lower() not in GENDER_RULE_VALUES:
            allowed = ", ".join(sorted(GENDER_RULE_VALUES))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Gender rule value must be one of: {allowed}",
            )

    elif parameter == EligibilityParameter.SOCIAL_CATEGORY:
        if cleaned.lower() not in SOCIAL_CATEGORY_RULE_VALUES:
            allowed = ", ".join(sorted(SOCIAL_CATEGORY_RULE_VALUES))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Social category rule value must be one of: "
                    f"{allowed}"
                ),
            )


def _require_government_official(current_user: User) -> None:
    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can manage schemes",
        )


def scheme_scope_criteria(scope: str):
    """Query criteria that keep a scheme inside an official's scope.

    A scheme belongs to the official's department when it carries that
    department itself, or when it sits under a policy of that ministry — the
    canonical rule from backend/app/scope.py, now case-insensitive and
    trimmed so list and detail can no longer disagree.
    """
    return scheme_scope_filter(scope)


def _scheme_is_in_scope(db: Session, scheme: Scheme, scope: str) -> bool:
    return (
        db.query(Scheme.id)
        .filter(Scheme.id == scheme.id, scheme_scope_criteria(scope))
        .first()
        is not None
    )


def _enforce_scheme_scope(
    db: Session,
    scheme: Scheme,
    scope: str,
) -> None:
    if not _scheme_is_in_scope(db, scheme, scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This scheme is outside your department scope",
        )


def _assert_scheme_is_visible(
    db: Session,
    scheme: Scheme,
    current_user: User,
) -> None:
    """Reject reads of schemes the caller may not see.

    Mirrors the discovery rules of `list_schemes`:

    * administrators see every status;
    * the creator (owner) always sees their own record;
    * everyone else only sees ACTIVE schemes (drafts, pending, rejected and
      archived records stay hidden).

    Officials are additionally locked to their own department/ministry. A
    record the caller may not see answers 404 (not 403) so its existence is
    not revealed; an out-of-scope official keeps the existing 403.
    """
    if current_user.role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        return

    if current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        scope = _get_official_ministry(db, current_user)
        _enforce_scheme_scope(db, scheme, scope)

    if (
        scheme.created_by == current_user.id
        or scheme.status == SchemeStatus.ACTIVE
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Scheme not found",
    )


def _enforce_scope(
    policy: Policy,
    scheme_department: str | None,
    scope: str,
) -> None:
    """Reject a scheme outside the official's own department/ministry.

    Used for both creation and for edits that move a scheme's department, so
    an official can never place (or push) a scheme outside their scope through
    the API.
    """
    if scheme_in_scope(scheme_department, policy.ministry, scope):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "You can only manage schemes for your own department/ministry "
            f'("{scope}")'
        ),
    )


def create_scheme(
    db: Session,
    scheme_data: SchemeCreate,
    current_user: User,
    request: Request | None = None,
) -> Scheme:
    _require_government_official(current_user)

    policy = db.get(Policy, scheme_data.policy_id)

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    if policy.status != PolicyStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheme can only be created under an approved policy",
        )

    scope = _get_official_ministry(db, current_user)
    _enforce_scope(policy, scheme_data.department, scope)

    launch_date = scheme_data.launch_date or date.today()

    # A deadline before the launch date would make the scheme unapplicable
    # from day one.
    if (
        scheme_data.deadline_date is not None
        and scheme_data.deadline_date < launch_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheme deadline date cannot be earlier than its launch date",
        )

    scheme = Scheme(
        policy_id=scheme_data.policy_id,
        title=scheme_data.title,
        description=scheme_data.description,
        required_documents=scheme_data.required_documents,
        category=scheme_data.category,
        benefits=scheme_data.benefits,
        application_process=scheme_data.application_process,
        department=scheme_data.department,
        state=scheme_data.state,
        status=SchemeStatus.PENDING_APPROVAL,
        launch_date=launch_date,
        deadline_date=scheme_data.deadline_date,
        document_url=scheme_data.document_url,
        created_by=current_user.id,
    )

    db.add(scheme)
    # Flush inside the same transaction so the server-generated id exists for
    # the notification below; nothing is committed until db.commit().
    db.flush()

    # Queued in the same transaction as the insert: the creator's "pending
    # approval" alert is published together with the scheme itself, and no
    # alert survives a failed commit.
    _notify_scheme_awaiting_approval(db, scheme, current_user)

    db.commit()
    db.refresh(scheme)

    try:
        schedule_scheme_sync(scheme.id, expected_updated_at=scheme.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for scheme %s: %s",
            scheme.id,
            exc,
        )

    return scheme


def get_scheme(
    db: Session,
    scheme_id: UUID,
) -> Scheme:
    scheme = db.get(Scheme, scheme_id)

    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheme not found",
        )

    return scheme


def _count_scheme_view(
    db: Session,
    scheme: Scheme,
    current_user: User,
) -> None:
    """Bump `view_count` for a visit that is actually counted.

    The increment happens in SQL (``view_count = view_count + 1``) so
    concurrent readers cannot lose an update. Views by the scheme's creator
    and by administrators are ignored, and callers only reach this after the
    visibility check, so requests that end in 403/404 never count.
    """
    if current_user.role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        return

    if scheme.created_by == current_user.id:
        return

    (
        db.query(Scheme)
        .filter(Scheme.id == scheme.id)
        .update(
            {Scheme.view_count: Scheme.view_count + 1},
            synchronize_session=False,
        )
    )
    db.commit()
    db.refresh(scheme)


def get_scheme_details(
    db: Session,
    scheme_id: UUID,
    current_user: User | None,
) -> Scheme:
    """Return scheme details for the read endpoint.

    Guests can view ACTIVE schemes only.
    Authenticated users retain their existing role-specific visibility rules.
    View counts are updated only for authenticated users.
    """
    scheme = get_scheme(db, scheme_id)

    if current_user is None:
        # Guests can view active schemes only.
        if scheme.status != SchemeStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheme not found",
            )
    else:
        _assert_scheme_is_visible(db, scheme, current_user)
        _count_scheme_view(db, scheme, current_user)

    return scheme



def list_schemes(
    db: Session,
    current_user: User | None,
    include_archived: bool = False,
    by_me: bool = False,
    include_expired: bool = False,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[Scheme], int]:
    """Schemes the caller may see, newest first, paged.

    Guests can see active schemes. Authenticated users retain their
    existing role-specific visibility rules.

    Returns (rows, total), where total counts matching rows before
    LIMIT/OFFSET, for the X-Total-Count header.
    """
    query = db.query(Scheme)

    if current_user is None:
        # Guests can see active schemes only.
        query = query.filter(
            Scheme.status == SchemeStatus.ACTIVE
        )

    elif current_user.role in (
        UserRole.ADMINISTRATOR,
        UserRole.SUPER_ADMIN,
    ):
        # Admins see all statuses, excluding archived by default.
        if not include_archived:
            query = query.filter(
                Scheme.status != SchemeStatus.ARCHIVED
            )

    elif current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        # Officials are restricted to their own department/ministry.
        scope = _get_official_ministry(db, current_user)
        query = query.filter(scheme_scope_criteria(scope))

        if by_me:
            query = query.filter(
                Scheme.created_by == current_user.id
            )
        else:
            query = query.filter(
                (Scheme.created_by == current_user.id)
                | (Scheme.status == SchemeStatus.ACTIVE)
            )

        if not include_archived:
            query = query.filter(
                Scheme.status != SchemeStatus.ARCHIVED
            )

    else:
        # Citizens, researchers, organizations: ACTIVE schemes only.
        query = query.filter(
            Scheme.status == SchemeStatus.ACTIVE
        )

    # Hide expired schemes by default from guests and public-facing roles.
    # include_expired=True allows expired ACTIVE schemes to appear.
    if not include_expired and (
        current_user is None
        or current_user.role in PUBLIC_SCHEME_ROLES
    ):
        query = query.filter(
            or_(
                Scheme.deadline_date.is_(None),
                Scheme.deadline_date >= date.today(),
            )
        )

    total = query.count()

    rows = (
        query.order_by(Scheme.created_at.desc())
        .offset(offset)
        .limit(clamp_limit(limit))
        .all()
    )

    return rows, total



def _notify_scheme_published(
    db: Session,
    scheme: Scheme,
    current_user: User,
) -> None:
    """Queue SCHEME_UPDATE notifications when a scheme becomes ACTIVE.
    """
    recipients = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            User.role.in_(SCHEME_UPDATE_RECIPIENT_ROLES),
            User.id != current_user.id,
        )
        .all()
    )

    for recipient in recipients:
        send_notification(
            db=db,
            user_id=recipient.id,
            notification_type=NotificationType.SCHEME_UPDATE,
            title="Scheme Published",
            message=(
                f'The scheme "{scheme.title}" is now available. '
                "Review the details before you apply."
            ),
            related_entity_type="scheme",
            related_entity_id=scheme.id,
        )


def _notify_scheme_awaiting_approval(
    db: Session,
    scheme: Scheme,
    current_user: User,
) -> None:
    """Queue APPROVAL_PENDING to the administrators when a scheme is created.

    Recipients come from one query and the rows are staged in the caller's
    open transaction, so the alert costs no query per administrator and is
    published together with the scheme. The creating official is excluded.
    """

    recipients = (
        db.query(User.id)
        .filter(
            User.is_active.is_(True),
            User.role == UserRole.ADMINISTRATOR,
            User.id != current_user.id,
        )
        .all()
    )

    if not recipients:
        return

    queue_notifications(
        db=db,
        user_ids=[row[0] for row in recipients],
        notification_type=NotificationType.APPROVAL_PENDING,
        title="Scheme Awaiting Approval",
        message=(
            f'The scheme "{scheme.title}" has been submitted and is '
            "waiting for approval."
        ),
        related_entity_type="scheme",
        related_entity_id=scheme.id,
    )


def _notify_scheme_creator_approved(
    db: Session,
    scheme: Scheme,
    current_user: User,
) -> None:
    """Queue SCHEME_APPROVED to the scheme's creator. Skips self-approval."""

    if not scheme.created_by or scheme.created_by == current_user.id:
        return

    queue_notifications(
        db=db,
        user_ids=[scheme.created_by],
        notification_type=NotificationType.SCHEME_APPROVED,
        title="Scheme Approved",
        message=f'Your scheme "{scheme.title}" has been approved and is now live.',
        related_entity_type="scheme",
        related_entity_id=scheme.id,
    )


def _notify_scheme_creator_rejected(
    db: Session,
    scheme: Scheme,
    current_user: User,
) -> None:
    """Queue SCHEME_REJECTED to the creator, carrying the stated reason."""

    if not scheme.created_by or scheme.created_by == current_user.id:
        return

    queue_notifications(
        db=db,
        user_ids=[scheme.created_by],
        notification_type=NotificationType.SCHEME_REJECTED,
        title="Scheme Rejected",
        message=(
            f'Your scheme "{scheme.title}" was rejected.\n'
            f"Reason: {scheme.rejection_reason}"
        ),
        related_entity_type="scheme",
        related_entity_id=scheme.id,
    )


def update_scheme(
    db: Session,
    scheme_id: UUID,
    scheme_data: SchemeUpdate,
    current_user: User,
) -> Scheme:
    _require_government_official(current_user)

    scheme = get_scheme(db, scheme_id)

    if scheme.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update schemes you created",
        )

    if scheme.status == SchemeStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active schemes cannot be updated. Archive the scheme first.",
        )

    if scheme.status == SchemeStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheme is pending approval and cannot be updated",
        )

    update_data = scheme_data.model_dump(exclude_unset=True)

    for field in NON_NULLABLE_UPDATE_FIELDS:
        if field in update_data and update_data[field] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} cannot be null",
            )

    if "department" in update_data:
        # The department may only be set within the official's own scope.
        scope = _get_official_ministry(db, current_user)
        policy = db.get(Policy, scheme.policy_id)
        _enforce_scope(policy, update_data.get("department"), scope)

    # Validate the dates as they will exist after the update: fields that are
    # not being changed keep their stored values.
    effective_launch = update_data.get("launch_date", scheme.launch_date)
    effective_deadline = update_data.get("deadline_date", scheme.deadline_date)

    if (
        effective_deadline is not None
        and effective_launch is not None
        and effective_deadline < effective_launch
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheme deadline date cannot be earlier than its launch date",
        )

    if scheme.status == SchemeStatus.ARCHIVED:
        for field, value in update_data.items():
            setattr(scheme, field, value)
        # Remains ARCHIVED after update
    elif scheme.status == SchemeStatus.REJECTED:
        for field, value in update_data.items():
            setattr(scheme, field, value)
        scheme.status = SchemeStatus.PENDING_APPROVAL
        scheme.rejection_reason = None
        scheme.approved_by = None
    else:
        for field, value in update_data.items():
            setattr(scheme, field, value)

    # No notification here: these edits happen on non-public schemes. The
    # SCHEME_UPDATE alert is sent when the scheme is approved instead.

    db.commit()
    db.refresh(scheme)

    try:
        schedule_scheme_sync(scheme.id, expected_updated_at=scheme.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for scheme %s: %s",
            scheme.id,
            exc,
        )

    return scheme


def archive_scheme(
    db: Session,
    scheme_id: UUID,
    current_user: User,
    request: Request | None = None,
) -> Scheme:
    _require_government_official(current_user)

    scheme = get_scheme(db, scheme_id)

    if scheme.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only archive schemes you created",
        )

    scope = _get_official_ministry(db, current_user)
    _enforce_scheme_scope(db, scheme, scope)

    if scheme.status == SchemeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheme is already archived",
        )

    old_status = scheme.status

    scheme.status = SchemeStatus.ARCHIVED
    scheme.archived_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        actor_id=current_user.id,
        action=AUDIT_SCHEME_ARCHIVE,
        target_table="schemes",
        target_id=scheme.id,
        changes={"status": {"old": old_status.value, "new": SchemeStatus.ARCHIVED.value}},
        ip_address=client_ip(request),
    )

    db.commit()
    db.refresh(scheme)

    try:
        schedule_scheme_sync(scheme.id, expected_updated_at=scheme.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for scheme %s: %s",
            scheme.id,
            exc,
        )

    return scheme


def unarchive_scheme(
    db: Session,
    scheme_id: UUID,
    current_user: User,
    request: Request | None = None,
) -> Scheme:
    _require_government_official(current_user)

    scheme = get_scheme(db, scheme_id)

    if scheme.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only unarchive schemes you created",
        )

    if scheme.status != SchemeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only archived schemes can be unarchived",
        )

    scheme.status = SchemeStatus.PENDING_APPROVAL
    scheme.archived_at = None
    scheme.approved_by = None
    scheme.rejection_reason = None

    log_action(
        db=db,
        actor_id=current_user.id,
        action=AUDIT_SCHEME_UNARCHIVE,
        target_table="schemes",
        target_id=scheme.id,
        changes={
            "status": {"old": SchemeStatus.ARCHIVED.value, "new": SchemeStatus.PENDING_APPROVAL.value}
        },
        ip_address=client_ip(request),
    )

    db.commit()
    db.refresh(scheme)

    try:
        schedule_scheme_sync(scheme.id, expected_updated_at=scheme.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for scheme %s: %s",
            scheme.id,
            exc,
        )

    return scheme


def approve_scheme(
    db: Session,
    scheme_id: UUID,
    current_user: User,
    request: Request | None = None,
) -> Scheme:
    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can approve schemes",
        )

    scheme = get_scheme(db, scheme_id)

    if scheme.status != SchemeStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending schemes can be approved",
        )

    scheme.status = SchemeStatus.ACTIVE
    scheme.approved_by = current_user.id
    scheme.rejection_reason = None

    # Existing public "Scheme Published" alert, unchanged.
    _notify_scheme_published(db, scheme, current_user)
    _notify_scheme_creator_approved(db, scheme, current_user)

    log_action(
        db=db,
        actor_id=current_user.id,
        action=AUDIT_SCHEME_APPROVE,
        target_table="schemes",
        target_id=scheme.id,
        changes={
            "status": {"old": SchemeStatus.PENDING_APPROVAL.value, "new": SchemeStatus.ACTIVE.value}
        },
        ip_address=client_ip(request),
    )

    db.commit()
    db.refresh(scheme)

    try:
        schedule_scheme_sync(scheme.id, expected_updated_at=scheme.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for scheme %s: %s",
            scheme.id,
            exc,
        )

    return scheme


def reject_scheme(
    db: Session,
    scheme_id: UUID,
    rejection_reason: str,
    current_user: User,
    request: Request | None = None,
) -> Scheme:
    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can reject schemes",
        )

    scheme = get_scheme(db, scheme_id)

    if scheme.status != SchemeStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending schemes can be rejected",
        )

    if not rejection_reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is required",
        )

    scheme.status = SchemeStatus.REJECTED
    scheme.rejection_reason = rejection_reason
    scheme.approved_by = None

    _notify_scheme_creator_rejected(db, scheme, current_user)

    log_action(
        db=db,
        actor_id=current_user.id,
        action=AUDIT_SCHEME_REJECT,
        target_table="schemes",
        target_id=scheme.id,
        changes={
            "status": {"old": SchemeStatus.PENDING_APPROVAL.value, "new": SchemeStatus.REJECTED.value}
        },
        ip_address=client_ip(request),
    )

    db.commit()
    db.refresh(scheme)

    try:
        schedule_scheme_sync(scheme.id, expected_updated_at=scheme.updated_at)
    except Exception as exc:
        # The authoritative transaction already committed; scheduling must not
        # fail the request, but the miss is never silent.
        logger.warning(
            "Knowledge sync scheduling failed for scheme %s: %s",
            scheme.id,
            exc,
        )

    return scheme


def create_eligibility_rule(
    db: Session,
    scheme_id: UUID,
    parameter: EligibilityParameter,
    operator: EligibilityOperator,
    value: str,
    current_user: User,
) -> EligibilityRule:
    _require_government_official(current_user)

    scheme = get_scheme(db, scheme_id)

    if scheme.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage rules for schemes you created",
        )

    if scheme.status == SchemeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add rules to an archived scheme",
        )

    if scheme.status in (
        SchemeStatus.ACTIVE,
        SchemeStatus.PENDING_APPROVAL,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add rules to an active or pending approval scheme",
        )

    _validate_rule_operator(parameter, operator)
    value = _validate_rule_value(parameter, value, operator)

    rule = EligibilityRule(
        scheme_id=scheme_id,
        parameter=parameter,
        operator=operator,
        value=value,
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    try:
        schedule_scheme_sync(scheme_id)
    except Exception as exc:
        logger.warning("Knowledge sync scheduling failed for scheme %s: %s", scheme_id, exc)

    return rule


def get_eligibility_rules(
    db: Session,
    scheme_id: UUID,
    current_user: User,
) -> list[EligibilityRule]:
    scheme = get_scheme(db, scheme_id)

    # Eligibility rules describe a scheme, so they follow exactly the same
    # visibility rules as the scheme itself.
    _assert_scheme_is_visible(db, scheme, current_user)

    return (
        db.query(EligibilityRule)
        .filter(EligibilityRule.scheme_id == scheme.id)
        .order_by(EligibilityRule.created_at.asc())
        .all()
    )


def update_eligibility_rule(
    db: Session,
    rule_id: UUID,
    parameter: EligibilityParameter | None,
    operator: EligibilityOperator | None,
    value: str | None,
    current_user: User,
) -> EligibilityRule:
    _require_government_official(current_user)

    rule = db.get(EligibilityRule, rule_id)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eligibility rule not found",
        )

    scheme = get_scheme(db, rule.scheme_id)

    if scheme.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage rules for schemes you created",
        )

    if scheme.status == SchemeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update rules of an archived scheme",
        )

    if scheme.status in (
        SchemeStatus.ACTIVE,
        SchemeStatus.PENDING_APPROVAL,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update rules of an active or pending approval scheme",
        )

    # Validate the state the rule will end up in: the fields being changed
    # plus the stored ones. The (parameter, operator) pair must be
    # compatible and the value must be valid for that pair — so changing
    # only the operator of an "in" rule to "eq" while the stored value is
    # still a list is rejected instead of silently stored.
    if parameter is not None or operator is not None or value is not None:
        effective_parameter = (
            parameter if parameter is not None else rule.parameter
        )
        effective_operator = (
            operator if operator is not None else rule.operator
        )
        effective_value = value if value is not None else rule.value

        _validate_rule_operator(effective_parameter, effective_operator)
        effective_value = _validate_rule_value(
            effective_parameter,
            effective_value,
            effective_operator,
        )

        rule.parameter = effective_parameter
        rule.operator = effective_operator
        rule.value = effective_value

    db.commit()
    db.refresh(rule)

    try:
        schedule_scheme_sync(rule.scheme_id)
    except Exception as exc:
        logger.warning(
            "Knowledge sync scheduling failed for scheme %s: %s",
            rule.scheme_id,
            exc,
        )

    return rule


def delete_eligibility_rule(
    db: Session,
    rule_id: UUID,
    current_user: User,
) -> None:
    _require_government_official(current_user)

    rule = db.get(EligibilityRule, rule_id)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eligibility rule not found",
        )

    scheme = get_scheme(db, rule.scheme_id)

    if scheme.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage rules for schemes you created",
        )

    if scheme.status == SchemeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete rules from an archived scheme",
        )

    if scheme.status in (
        SchemeStatus.ACTIVE,
        SchemeStatus.PENDING_APPROVAL,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete rules from an active or pending approval scheme",
        )

    target_scheme_id = rule.scheme_id
    db.delete(rule)
    db.commit()

    try:
        schedule_scheme_sync(target_scheme_id)
    except Exception as exc:
        logger.warning(
            "Knowledge sync scheduling failed for scheme %s: %s",
            target_scheme_id,
            exc,
        )
