import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

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
from backend.app.notifications.service import send_notification
from backend.app.schemes.schemas import SchemeCreate, SchemeUpdate
# Reuses the existing department-scope rule (profile department, 403 when the
# profile is missing) the analytics, reports and applications modules already
# apply to government officials.
from backend.app.ai.sync_service import schedule_scheme_sync
from backend.app.analytics.service import _get_official_ministry

logger = logging.getLogger(__name__)

# Audience for SCHEME_UPDATE alerts: the same roles that receive NEW_POLICY
# alerts when a policy is approved, so citizens/researchers/organizations are
# informed about scheme changes without widening the existing audience.
SCHEME_UPDATE_RECIPIENT_ROLES = (
    UserRole.CITIZEN,
    UserRole.RESEARCHER,
    UserRole.ORGANIZATION,
)

# Columns of `schemes` that are NOT NULL in the database. An explicit JSON
# null for one of them would otherwise be written through and fail with an
# IntegrityError (500) at commit; the API rejects it up front instead — the
# same rule the FAQ module applies to its update endpoint.
NON_NULLABLE_UPDATE_FIELDS = ("title", "description", "category")

# Values the enumerated parameters accept. Numeric parameters are parsed and
# the free-text ones only have to be non-empty, so every stored rule value is
# valid for its parameter and evaluation can never crash on bad input.
GENDER_RULE_VALUES = {gender.value for gender in Gender}
SOCIAL_CATEGORY_RULE_VALUES = {
    category.value for category in SocialCategory
}


def _validate_rule_value(
    parameter: EligibilityParameter,
    value: str,
) -> str:
    """Validate a rule value against its parameter, returning it stripped.

    Raises 400 with a client-safe message instead of storing a value that
    would raise when the eligibility rules are evaluated later.
    """
    cleaned = value.strip()

    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rule value is required for {parameter.value}",
        )

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

    return cleaned


def _require_government_official(current_user: User) -> None:
    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can manage schemes",
        )


def scheme_scope_criteria(scope: str):
    """Query criteria that keep a scheme inside an official's scope.

    A scheme belongs to the official's department when it carries that
    department itself, or when it sits under a policy of that ministry. This
    mirrors the scope rule the application-review module already applies.
    """
    return or_(
        Scheme.department == scope,
        Scheme.policy_id.in_(
            select(Policy.id).where(Policy.ministry == scope)
        ),
    )


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
    if policy.ministry == scope:
        return

    submitted = (scheme_department or "").strip()

    if submitted and submitted.casefold() == scope.strip().casefold():
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


def get_scheme_details(
    db: Session,
    scheme_id: UUID,
    current_user: User,
) -> Scheme:
    """Scheme detail for the read endpoint.

    Hidden records (non-ACTIVE schemes the caller does not own) answer 404;
    officials are additionally locked to their own department/ministry.
    """
    scheme = get_scheme(db, scheme_id)
    _assert_scheme_is_visible(db, scheme, current_user)

    return scheme


def list_schemes(
    db: Session,
    current_user: User,
    include_archived: bool = False,
    by_me: bool = False,
) -> list[Scheme]:
    query = db.query(Scheme)

    if current_user.role in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        # Admins see all statuses from all users; `by_me` is only offered to
        # officials, so their behaviour is unchanged.
        if not include_archived:
            query = query.filter(Scheme.status != SchemeStatus.ARCHIVED)
    elif current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        # Officials are locked to their own department/ministry. Inside that
        # scope they see their own records (all statuses) + ACTIVE records
        # from others, or only their own records when "By Me" is selected.
        scope = _get_official_ministry(db, current_user)
        query = query.filter(scheme_scope_criteria(scope))
        if by_me:
            query = query.filter(Scheme.created_by == current_user.id)
        else:
            query = query.filter(
                (Scheme.created_by == current_user.id)
                | (Scheme.status == SchemeStatus.ACTIVE)
            )
        if not include_archived:
            query = query.filter(Scheme.status != SchemeStatus.ARCHIVED)
    else:
        # Citizens, researchers, organizations: ACTIVE only
        query = query.filter(Scheme.status == SchemeStatus.ACTIVE)

    return query.order_by(
        Scheme.created_at.desc()
    ).all()


def _notify_scheme_published(
    db: Session,
    scheme: Scheme,
    current_user: User,
) -> None:
    """Queue SCHEME_UPDATE notifications when a scheme becomes ACTIVE.

    Only approved schemes are public. Edits happen on draft, rejected or
    archived schemes, which citizens cannot see, so notifying on an edit
    would alert people about schemes that do not exist for them. The alert is
    sent on approval instead — the moment the scheme becomes available.

    The notifications are added to the same session as the status change, so
    a failed commit leaves neither the approval nor the notifications behind.
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

    scheme.status = SchemeStatus.ARCHIVED
    scheme.archived_at = datetime.utcnow()

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

    _notify_scheme_published(db, scheme, current_user)

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

    value = _validate_rule_value(parameter, value)

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

    # The value is validated against the parameter it will end up with: the
    # one being changed to, or the existing one when only the value changes.
    # A parameter change also has to keep the stored value valid.
    if value is not None:
        effective_parameter = (
            parameter if parameter is not None else rule.parameter
        )
        value = _validate_rule_value(effective_parameter, value)
    elif parameter is not None:
        rule.value = _validate_rule_value(parameter, rule.value)

    if parameter is not None:
        rule.parameter = parameter

    if operator is not None:
        rule.operator = operator

    if value is not None:
        rule.value = value

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
