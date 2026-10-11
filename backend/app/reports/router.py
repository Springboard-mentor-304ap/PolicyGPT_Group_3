from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.pagination import DEFAULT_LIMIT
from backend.app.reports.schemas import ReportGenerateRequest, ReportResponse
from backend.app.reports.service import (
    REPORT_ALLOWED_ROLES,
    REPORT_MEDIA_TYPES,
    build_download_filename,
    generate_report,
    get_report,
    get_report_file,
    list_reports,
)


# Check whether the logged-in user is allowed to use the Reports module
def require_report_access(
    current_user: User = Depends(get_current_user),
) -> User:

    if current_user.role not in REPORT_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access reports",
        )

    return current_user


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
    dependencies=[Depends(require_report_access)],
)


@router.post(
    "/generate",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_report_route(
    report_request: ReportGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_report_access),
):
    return generate_report(
        db=db,
        report_request=report_request,
        current_user=current_user,
        request=request,
    )


@router.get(
    "",
    response_model=list[ReportResponse],
)
def list_reports_route(
    response: Response,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_report_access),
):
    rows, total = list_reports(
        db=db,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )

    response.headers["X-Total-Count"] = str(total)

    return rows


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
)
def get_report_route(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_report_access),
):
    return get_report(
        db=db,
        report_id=report_id,
        current_user=current_user,
    )


@router.get(
    "/{report_id}/download",
)
def download_report_route(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_report_access),
):
    report = get_report(
        db=db,
        report_id=report_id,
        current_user=current_user,
    )
    file_path = get_report_file(report)

    return FileResponse(
        path=file_path,
        media_type=REPORT_MEDIA_TYPES[report.format],
        filename=build_download_filename(report),
    )
