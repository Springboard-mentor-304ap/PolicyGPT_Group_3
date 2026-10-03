from datetime import date, datetime
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
from backend.app.notifications.service import send_notification
from backend.app.schemes.schemas import SchemeCreate, SchemeUpdate
# Reuses the existing department-scope rule (profile department, 403 when the
# profile is missing) the analytics, reports and applications modules already
# apply to government officials.
from backend.app.analytics.service import _get_official_ministry

# Audience for SCHEME_UPDATE alerts: the same roles that receive NEW_POLICY
# alerts when a policy is approved, so citizens/researchers/organizations are
# informed about scheme changes without widening the existing audience.
SCHEME_UPDATE_RECIPIENT_ROLES = (
    UserRole.CITIZEN,
    UserRole.RESEARCHER,
    UserRole.ORGANIZATION,
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

    scheme = Scheme(
        policy_id=scheme_data.policy_id,
        title=scheme_data.title,
        description=scheme_data.description,
        category=scheme_data.category,
        benefits=scheme_data.benefits,
        application_process=scheme_data.application_process,
        department=scheme_data.department,
        state=scheme_data.state,
        status=SchemeStatus.PENDING_APPROVAL,
        launch_date=scheme_data.launch_date or date.today(),
        deadline_date=scheme_data.deadline_date,
        document_url=scheme_data.document_url,
        created_by=current_user.id,
    )

    db.add(scheme)
    db.commit()
    db.refresh(scheme)

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

    Officials can only open schemes of their own department/ministry;
    administrators and the public discovery roles stay unrestricted.
    """
    scheme = get_scheme(db, scheme_id)

    if current_user.role == UserRole.GOVERNMENT_OFFICIAL:
        scope = _get_official_ministry(db, current_user)
        _enforce_scheme_scope(db, scheme, scope)

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


def _notify_scheme_update(
    db: Session,
    scheme: Scheme,
    current_user: User,
) -> None:
    """Queue SCHEME_UPDATE notifications within the caller's transaction.

    The notifications are added to the same session as the scheme change, so a
    failed commit leaves neither the edit nor the notifications behind, and a
    single edit can never generate the same notification twice.
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
            title="Scheme Updated",
            message=(
                f'The scheme "{scheme.title}" has been updated. '
                "Review the latest details before you apply."
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
    scheme = get_scheme(db, scheme_id)

    _require_government_official(current_user)

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

    if "department" in update_data:
        # The department may only be set within the official's own scope.
        scope = _get_official_ministry(db, current_user)
        policy = db.get(Policy, scheme.policy_id)
        _enforce_scope(policy, update_data.get("department"), scope)

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

    if update_data:
        _notify_scheme_update(db, scheme, current_user)

    db.commit()
    db.refresh(scheme)

    return scheme


def archive_scheme(
    db: Session,
    scheme_id: UUID,
    current_user: User,
) -> Scheme:
    scheme = get_scheme(db, scheme_id)

    _require_government_official(current_user)

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

    return scheme


def unarchive_scheme(
    db: Session,
    scheme_id: UUID,
    current_user: User,
) -> Scheme:
    scheme = get_scheme(db, scheme_id)

    _require_government_official(current_user)

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

    return scheme


def approve_scheme(
    db: Session,
    scheme_id: UUID,
    current_user: User,
) -> Scheme:
    scheme = get_scheme(db, scheme_id)

    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can approve schemes",
        )

    if scheme.status != SchemeStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending schemes can be approved",
        )

    scheme.status = SchemeStatus.ACTIVE
    scheme.approved_by = current_user.id
    scheme.rejection_reason = None

    db.commit()
    db.refresh(scheme)

    return scheme


def reject_scheme(
    db: Session,
    scheme_id: UUID,
    rejection_reason: str,
    current_user: User,
) -> Scheme:
    scheme = get_scheme(db, scheme_id)

    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can reject schemes",
        )

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

    return scheme


def create_eligibility_rule(
    db: Session,
    scheme_id: UUID,
    parameter: EligibilityParameter,
    operator: EligibilityOperator,
    value: str,
    current_user: User,
) -> EligibilityRule:
    scheme = get_scheme(db, scheme_id)

    _require_government_official(current_user)

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

    rule = EligibilityRule(
        scheme_id=scheme_id,
        parameter=parameter,
        operator=operator,
        value=value,
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule


def get_eligibility_rules(
    db: Session,
    scheme_id: UUID,
) -> list[EligibilityRule]:
    scheme = get_scheme(db, scheme_id)

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
    rule = db.get(EligibilityRule, rule_id)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eligibility rule not found",
        )

    scheme = get_scheme(db, rule.scheme_id)

    _require_government_official(current_user)

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

    if parameter is not None:
        rule.parameter = parameter

    if operator is not None:
        rule.operator = operator

    if value is not None:
        rule.value = value

    db.commit()
    db.refresh(rule)

    return rule


def delete_eligibility_rule(
    db: Session,
    rule_id: UUID,
    current_user: User,
) -> None:
    rule = db.get(EligibilityRule, rule_id)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eligibility rule not found",
        )

    scheme = get_scheme(db, rule.scheme_id)

    _require_government_official(current_user)

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

    db.delete(rule)
    db.commit()
