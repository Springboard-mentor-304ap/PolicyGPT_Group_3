from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.faq.schemas import FAQCreate, FAQResponse, FAQUpdate
from backend.app.faq.service import (
    create_faq,
    deactivate_faq,
    get_faq,
    list_faqs,
    update_faq,
)
from backend.app.models.user import User

router = APIRouter(
    prefix="/faqs",
    tags=["FAQ"],
)


@router.post(
    "",
    response_model=FAQResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_faq_route(
    faq_data: FAQCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_faq(
        db=db,
        faq_data=faq_data,
        current_user=current_user,
    )


@router.get(
    "",
    response_model=list[FAQResponse],
)
def list_faqs_route(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_faqs(
        db=db,
        current_user=current_user,
        search=search,
        category=category,
        include_inactive=include_inactive,
    )


@router.get(
    "/{faq_id}",
    response_model=FAQResponse,
)
def get_faq_route(
    faq_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_faq(
        db=db,
        faq_id=faq_id,
        current_user=current_user,
    )


@router.patch(
    "/{faq_id}",
    response_model=FAQResponse,
)
def update_faq_route(
    faq_id: UUID,
    faq_data: FAQUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_faq(
        db=db,
        faq_id=faq_id,
        faq_data=faq_data,
        current_user=current_user,
    )


@router.delete(
    "/{faq_id}",
    response_model=FAQResponse,
)
def deactivate_faq_route(
    faq_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return deactivate_faq(
        db=db,
        faq_id=faq_id,
        current_user=current_user,
    )
