from datetime import date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
    EligibilityRule,
)
from backend.app.models.policy import Policy, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.user import User, UserRole
from backend.app.schemes.schemas import SchemeCreate, SchemeUpdate


def _require_government_official(current_user: User) -> None:
    if current_user.role != UserRole.GOVERNMENT_OFFICIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only government officials can manage schemes",
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


def list_schemes(
    db: Session,
    include_archived: bool = False,
) -> list[Scheme]:
    query = db.query(Scheme)

    if not include_archived:
        query = query.filter(
            Scheme.status != SchemeStatus.ARCHIVED
        )

    return query.order_by(
        Scheme.created_at.desc()
    ).all()


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

    if scheme.status == SchemeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archived schemes cannot be updated",
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

    if scheme.status == SchemeStatus.REJECTED:
        for field, value in update_data.items():
            setattr(scheme, field, value)
        scheme.status = SchemeStatus.PENDING_APPROVAL
        scheme.rejection_reason = None
        scheme.approved_by = None
    else:
        for field, value in update_data.items():
            setattr(scheme, field, value)

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
