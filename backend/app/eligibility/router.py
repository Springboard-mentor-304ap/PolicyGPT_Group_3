from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.eligibility.schemas import EligibilityCheckResponse
from backend.app.eligibility.service import check_eligibility

router = APIRouter(
    prefix="/eligibility",
    tags=["Eligibility"],
)

@router.get(
    "/schemes/{scheme_id}",
    response_model=EligibilityCheckResponse,
)
def check_scheme_eligibility(
    scheme_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:

        return check_eligibility(
            db=db,
            current_user=current_user,
            scheme_id=scheme_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )