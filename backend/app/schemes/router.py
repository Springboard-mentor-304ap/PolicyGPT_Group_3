from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
)
from backend.app.models.user import User
from backend.app.schemes.schemas import (
    EligibilityRuleCreate,
    EligibilityRuleResponse,
    EligibilityRuleUpdate,
    SchemeCreate,
    SchemeReject,
    SchemeResponse,
    SchemeUpdate,
)
from backend.app.schemes.service import (
    approve_scheme,
    archive_scheme,
    create_eligibility_rule,
    create_scheme,
    delete_eligibility_rule,
    get_eligibility_rules,
    get_scheme,
    list_schemes,
    reject_scheme,
    unarchive_scheme,
    update_eligibility_rule,
    update_scheme,
)

router = APIRouter(prefix="/schemes", tags=["Schemes"])


@router.post("", response_model=SchemeResponse, status_code=status.HTTP_201_CREATED)
def create_scheme_route(
    scheme_data: SchemeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_scheme(
        db=db,
        scheme_data=scheme_data,
        current_user=current_user,
    )


@router.get("", response_model=list[SchemeResponse])
def list_schemes_route(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_schemes(
        db=db,
        current_user=current_user,
        include_archived=include_archived,
    )


@router.get("/{scheme_id}", response_model=SchemeResponse)
def get_scheme_route(
    scheme_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_scheme(
        db=db,
        scheme_id=scheme_id,
    )


@router.put("/{scheme_id}", response_model=SchemeResponse)
def update_scheme_route(
    scheme_id: UUID,
    scheme_data: SchemeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_scheme(
        db=db,
        scheme_id=scheme_id,
        scheme_data=scheme_data,
        current_user=current_user,
    )


@router.post("/{scheme_id}/archive", response_model=SchemeResponse)
def archive_scheme_route(
    scheme_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return archive_scheme(
        db=db,
        scheme_id=scheme_id,
        current_user=current_user,
    )


@router.post("/{scheme_id}/unarchive", response_model=SchemeResponse)
def unarchive_scheme_route(
    scheme_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return unarchive_scheme(
        db=db,
        scheme_id=scheme_id,
        current_user=current_user,
    )


@router.post("/{scheme_id}/approve", response_model=SchemeResponse)
def approve_scheme_route(
    scheme_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return approve_scheme(
        db=db,
        scheme_id=scheme_id,
        current_user=current_user,
    )


@router.post("/{scheme_id}/reject", response_model=SchemeResponse)
def reject_scheme_route(
    scheme_id: UUID,
    rejection_data: SchemeReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return reject_scheme(
        db=db,
        scheme_id=scheme_id,
        rejection_reason=rejection_data.rejection_reason,
        current_user=current_user,
    )


@router.post(
    "/{scheme_id}/eligibility-rules",
    response_model=EligibilityRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_eligibility_rule_route(
    scheme_id: UUID,
    rule_data: EligibilityRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_eligibility_rule(
        db=db,
        scheme_id=scheme_id,
        parameter=rule_data.parameter,
        operator=rule_data.operator,
        value=rule_data.value,
        current_user=current_user,
    )


@router.get(
    "/{scheme_id}/eligibility-rules",
    response_model=list[EligibilityRuleResponse],
)
def get_eligibility_rules_route(
    scheme_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_eligibility_rules(
        db=db,
        scheme_id=scheme_id,
    )


@router.put(
    "/eligibility-rules/{rule_id}",
    response_model=EligibilityRuleResponse,
)
def update_eligibility_rule_route(
    rule_id: UUID,
    rule_data: EligibilityRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_eligibility_rule(
        db=db,
        rule_id=rule_id,
        parameter=rule_data.parameter,
        operator=rule_data.operator,
        value=rule_data.value,
        current_user=current_user,
    )


@router.delete(
    "/eligibility-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_eligibility_rule_route(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delete_eligibility_rule(
        db=db,
        rule_id=rule_id,
        current_user=current_user,
    )
