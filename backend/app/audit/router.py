from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.audit.schemas import AuditLogResponse
from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.audit_log import AuditLog
from backend.app.models.user import User, UserRole

# The audit trail is administrative: only these two roles may read it.
AUDIT_LOG_ROLES = (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN)

# Paging bounds. 50 per page keeps a default response small, and 200 is a
# hard ceiling so a client cannot ask for the whole table in one request.
DEFAULT_LIMIT = 50
MAX_LIMIT = 200

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"],
)


def require_audit_access(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in AUDIT_LOG_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view audit logs",
        )

    return current_user


def _day_bounds(start: date | None, end: date | None):
    """Inclusive [date_from, date_to] as UTC day boundaries."""
    lower = (
        datetime.combine(start, time.min, tzinfo=timezone.utc) if start else None
    )

    if end:
        # +1 day makes the end date inclusive of its whole day.
        upper = datetime.combine(
            end + timedelta(days=1), time.min, tzinfo=timezone.utc
        )
    else:
        upper = None

    return lower, upper


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    response: Response,
    actor_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    target_table: str | None = Query(default=None),
    target_id: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_audit_access),
):
    query = db.query(AuditLog)

    if actor_id is not None:
        query = query.filter(AuditLog.actor_id == actor_id)

    if action is not None:
        query = query.filter(AuditLog.action == action)

    if target_table is not None:
        query = query.filter(AuditLog.target_table == target_table)

    if target_id is not None:
        query = query.filter(AuditLog.target_id == target_id)

    lower, upper = _day_bounds(date_from, date_to)

    if lower is not None:
        query = query.filter(AuditLog.created_at >= lower)

    if upper is not None:
        query = query.filter(AuditLog.created_at < upper)

    # The total counts every matching row, independent of paging, and is sent
    # in X-Total-Count so a client can build a pager without a second call.
    total = query.count()

    rows = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(min(limit, MAX_LIMIT))
        .all()
    )

    response.headers["X-Total-Count"] = str(total)

    return rows
