from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.comparison.schemas import (
    ComparisonRequest,
    ComparisonResponse,
)
from backend.app.comparison.service import compare_items
from backend.app.db.database import get_db


router = APIRouter(prefix="/comparison", tags=["Comparison"])


@router.post("", response_model=ComparisonResponse)
def compare(
    request: ComparisonRequest,
    db: Session = Depends(get_db),
):
    try:
        items = compare_items(
            db=db,
            request=request,
        )

        return ComparisonResponse(items=items)

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )