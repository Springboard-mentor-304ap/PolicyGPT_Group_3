from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.departments.schemas import DepartmentOptionsResponse
from backend.app.departments.service import list_departments
from backend.app.models.user import User

router = APIRouter(
    prefix="/departments",
    tags=["Departments"],
)


@router.get(
    "",
    response_model=DepartmentOptionsResponse,
)
def list_departments_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Department values that can be picked when creating or filtering records.

    Any authenticated user may read the list: the same names are already
    returned with every policy and scheme payload.
    """
    return DepartmentOptionsResponse(departments=list_departments(db))
