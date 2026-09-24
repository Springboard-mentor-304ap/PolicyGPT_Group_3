from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.faq.schemas import FAQCreate, FAQUpdate
from backend.app.models.faq import FAQ
from backend.app.models.user import User, UserRole


# Roles allowed to create, update and deactivate FAQs
FAQ_MANAGER_ROLES = (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN)

# Fields that must never be explicitly set to null on update
NON_NULLABLE_UPDATE_FIELDS = ("question", "answer", "is_active")


def _ensure_manager(current_user: User) -> None:
    if current_user.role not in FAQ_MANAGER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage FAQs",
        )


def _load_faq(db: Session, faq_id: UUID) -> FAQ:
    faq = db.get(FAQ, faq_id)

    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ not found",
        )

    return faq


def create_faq(
    db: Session,
    faq_data: FAQCreate,
    current_user: User,
) -> FAQ:
    _ensure_manager(current_user)

    faq = FAQ(
        question=faq_data.question,
        answer=faq_data.answer,
        category=faq_data.category,
        is_active=True,
        created_by=current_user.id,
        updated_by=None,
    )

    db.add(faq)
    db.commit()
    db.refresh(faq)

    return faq


def list_faqs(
    db: Session,
    current_user: User,
    search: str | None = None,
    category: str | None = None,
    include_inactive: bool = False,
) -> list[FAQ]:
    is_manager = current_user.role in FAQ_MANAGER_ROLES

    if include_inactive and not is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view inactive FAQs",
        )

    query = db.query(FAQ)

    if not include_inactive:
        query = query.filter(FAQ.is_active.is_(True))

    if category is not None:
        query = query.filter(FAQ.category == category)

    if search is not None:
        search_term = search.strip()
        if search_term:
            pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    FAQ.question.ilike(pattern),
                    FAQ.answer.ilike(pattern),
                )
            )

    return query.order_by(FAQ.created_at.desc()).all()


def get_faq(
    db: Session,
    faq_id: UUID,
    current_user: User,
) -> FAQ:
    faq = _load_faq(db, faq_id)

    if not faq.is_active and current_user.role not in FAQ_MANAGER_ROLES:
        # Inactive FAQs are hidden from non-managers
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ not found",
        )

    return faq


def update_faq(
    db: Session,
    faq_id: UUID,
    faq_data: FAQUpdate,
    current_user: User,
) -> FAQ:
    _ensure_manager(current_user)

    faq = _load_faq(db, faq_id)

    update_data = faq_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported fields were provided for update",
        )

    for field in NON_NULLABLE_UPDATE_FIELDS:
        if field in update_data and update_data[field] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} cannot be null",
            )

    for field, value in update_data.items():
        setattr(faq, field, value)

    faq.updated_by = current_user.id

    db.commit()
    db.refresh(faq)

    return faq


def deactivate_faq(
    db: Session,
    faq_id: UUID,
    current_user: User,
) -> FAQ:
    _ensure_manager(current_user)

    faq = _load_faq(db, faq_id)

    if not faq.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FAQ is already inactive",
        )

    faq.is_active = False
    faq.updated_by = current_user.id

    db.commit()
    db.refresh(faq)

    return faq
